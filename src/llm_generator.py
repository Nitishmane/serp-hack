from openai import (
    OpenAI,
    APITimeoutError,
    RateLimitError,
    AuthenticationError,
    APIConnectionError,
    APIStatusError,
)
import json


# OpenRouter exposes an OpenAI-compatible API, so we drive it with the openai SDK
# pointed at OpenRouter's base URL. Any model slug OpenRouter supports works here.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-5.3-flash"


class LLMError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ListingGenerator:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            # Optional OpenRouter attribution headers (used for their rankings).
            default_headers={"X-Title": "Amazon FBA Listing Generator"},
        )
        self.model = model

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Trim to <= limit chars, preferring a sentence then word boundary."""
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        # Prefer ending at a sentence boundary within the limit (no ellipsis needed).
        cut = text[:limit]
        for sep in (". ", "! ", "? "):
            idx = cut.rfind(sep)
            if idx >= limit * 0.6:
                return cut[:idx + 1].strip()
        # Otherwise trim to a word boundary, reserving one char for the ellipsis.
        cut = text[:limit - 1]
        sp = cut.rfind(" ")
        if sp >= limit * 0.5:
            cut = cut[:sp]
        return cut.strip().rstrip(",;:-") + "…"

    @staticmethod
    def _format_research_brief(context: dict = None) -> str:
        """Turn the competitor research context into a compact prompt section."""
        if not context:
            return ""
        lines = []

        titles = context.get("competitor_titles") or []
        if titles:
            lines.append("\nTop Amazon competitor titles:")
            lines.extend(f"- {t}" for t in titles[:8])

        stats = context.get("price_stats") or None
        if stats:
            lines.append(
                f"\nCompetitor prices (USD): low ${stats.get('min')}, "
                f"median ${stats.get('median')}, high ${stats.get('max')} "
                f"across {stats.get('count')} listings."
            )

        top_rated = context.get("top_rated") or []
        if top_rated:
            lines.append("\nHighly-rated competitors (rating / reviews):")
            lines.extend(
                f"- {r.get('title', '')[:70]} — {r.get('rating')}★ ({r.get('reviews')} reviews)"
                for r in top_rated[:3]
            )

        autocomplete = context.get("autocomplete") or []
        if autocomplete:
            lines.append("\nWhat shoppers search for (autocomplete):")
            lines.append("- " + "; ".join(autocomplete[:10]))

        return "\n".join(lines) + "\n" if lines else ""

    def generate_listing(self, product_name: str, keywords: list, context: dict = None) -> dict:
        """
        Use OpenAI-style tool calling (via OpenRouter) to generate a structured listing.

        context (optional) carries competitor research to inform positioning:
            {"competitor_titles": [...], "price_stats": {...},
             "top_rated": [...], "autocomplete": [...]}

        Returns: {"title", "description", "bullets", "suggested_price", "positioning"}
        Raises: LLMError on API failure or invalid tool response
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "GenerateListing",
                    "description": "Generate an SEO-optimized Amazon product listing informed by competitor research.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Amazon listing title (max 200 chars)"
                            },
                            "description": {
                                "type": "string",
                                "description": "Product description (max 300 chars)"
                            },
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "4-5 key feature/benefit bullets (each max 100 chars)"
                            },
                            "suggested_price": {
                                "type": "string",
                                "description": "Suggested retail price or range in USD (e.g. '$21.99' or '$18-24'), informed by competitor prices when available"
                            },
                            "positioning": {
                                "type": "string",
                                "description": "1-2 sentences on how to position this product against the competitors found (max 300 chars)"
                            }
                        },
                        "required": ["title", "description", "bullets", "suggested_price", "positioning"]
                    }
                }
            }
        ]

        keywords_str = ", ".join(keywords)
        research_brief = self._format_research_brief(context)
        user_msg = f"""
Product name: {product_name}

SEO keywords extracted from competitor research:
{keywords_str}
{research_brief}
Generate an Amazon listing for this product. Weave the keywords in naturally,
and use the competitor research to choose a competitive price and a sharp
positioning angle. Call the GenerateListing tool with your response.
"""

        system_prompt = """You are an expert Amazon product listing copywriter who specializes in
SEO-optimized titles and descriptions that maximize search visibility and
conversion on Amazon.

Your task is to generate a complete listing (title, description, 4-5 bullets,
a suggested price, and a positioning angle) for an Amazon product, using the
provided keywords and competitor research naturally where appropriate.

When competitor prices are provided, pick a suggested_price that is genuinely
competitive within that range. Use the competitor titles to find a positioning
angle that differentiates this product rather than repeating what everyone says.

Write rich, benefit-driven copy that uses close to the full space allowed.
Do not stop short — a listing that barely fills half the space looks thin and
converts worse. Target these ranges (and never exceed the hard maximums):
- Title: 150-200 characters (hard max 200)
- Description: 240-300 characters — a full, flowing paragraph, not one sentence (hard max 300)
- Bullets: 4-5 bullets, each 70-100 characters (hard max 100 each)

Use power words and urgency where sensible (e.g., "Premium", "Best-selling",
"Eco-friendly"). Return your response by calling the GenerateListing tool
with valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                # GLM 5.3 Flash is a reasoning model and reasoning cannot be disabled.
                # Reasoning tokens are counted against max_tokens, so keep a generous
                # budget or the tool-call arguments get truncated to an empty object.
                max_tokens=3000,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "GenerateListing"}},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                # "low" effort keeps latency to a few seconds and reserves budget for
                # the actual tool output. Passed via extra_body since it's an
                # OpenRouter-specific parameter, not part of the OpenAI schema.
                extra_body={"reasoning": {"effort": "low"}},
            )

            choice = response.choices[0]

            # If generation was cut off by the token limit, the tool arguments come
            # back empty/truncated. Surface that clearly instead of a vague error.
            if choice.finish_reason == "length":
                raise LLMError("Model response was truncated (token limit). Try again.", 502)

            tool_calls = choice.message.tool_calls or []
            if not tool_calls:
                raise LLMError("Model did not call GenerateListing tool", 502)

            # OpenAI-style tool arguments arrive as a JSON string; parse defensively
            # (strict=False tolerates raw control characters the model may emit).
            raw_args = tool_calls[0].function.arguments
            try:
                input_dict = json.loads(raw_args or "", strict=False)
            except (json.JSONDecodeError, TypeError):
                raise LLMError("Model returned invalid tool arguments", 502)
            if not isinstance(input_dict, dict):
                raise LLMError("Model returned invalid tool arguments", 502)

            # Validate required fields; enforce Amazon limits by trimming (not failing)
            # so an over-eager model doesn't 500 the whole request.
            for field in ("title", "description", "bullets"):
                if field not in input_dict:
                    raise LLMError(f"Model tool response missing '{field}'", 500)

            bullets = [b for b in (input_dict.get("bullets") or []) if b]
            return {
                "title": self._truncate(input_dict["title"], 200),
                "description": self._truncate(input_dict["description"], 300),
                "bullets": [self._truncate(b, 100) for b in bullets],
                "suggested_price": input_dict.get("suggested_price"),
                "positioning": self._truncate(input_dict.get("positioning", ""), 300) or None,
            }

        except LLMError:
            # Re-raise our own LLMError
            raise
        except APITimeoutError:
            raise LLMError("OpenRouter API timeout", 504)
        except RateLimitError:
            raise LLMError("OpenRouter rate limited", 429)
        except AuthenticationError:
            raise LLMError("Invalid OpenRouter key", 401)
        except APIConnectionError:
            raise LLMError("OpenRouter unreachable", 503)
        except APIStatusError as e:
            raise LLMError(f"OpenRouter API error: {e.message}", e.status_code or 500)
        except Exception as e:
            # Unexpected error
            raise LLMError(f"Unexpected error: {str(e)}", 500)
