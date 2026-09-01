from anthropic import Anthropic, APITimeoutError, RateLimitError, AuthenticationError, APIStatusError
import json


class ClaudeError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ClaudeGenerator:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
    
    def generate_listing(self, product_name: str, keywords: list) -> dict:
        """
        Use tool-use to generate structured listing.
        
        Returns: {"title": "...", "description": "...", "bullets": [...]}
        Raises: ClaudeError on API failure or invalid tool response
        """
        tools = [
            {
                "name": "GenerateListing",
                "description": "Generate an Amazon product listing with title, description, and bullets.",
                "input_schema": {
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
                            "description": "3-5 key feature/benefit bullets (each max 100 chars)"
                        }
                    },
                    "required": ["title", "description", "bullets"]
                }
            }
        ]
        
        keywords_str = ", ".join(keywords)
        user_msg = f"""
Product name: {product_name}

SEO keywords extracted from competitor research:
{keywords_str}

Generate an Amazon listing for this product using the keywords above. 
Call the GenerateListing tool with your response.
"""
        
        system_prompt = """You are an expert Amazon product listing copywriter who specializes in 
SEO-optimized titles and descriptions that maximize search visibility and 
conversion on Amazon.

Your task is to generate a complete listing (title, description, 3-5 bullets) 
for an Amazon product, using the provided keywords naturally where appropriate.

Respect Amazon's character limits strictly:
- Title: max 200 characters
- Description: max 300 characters
- Each bullet: max 100 characters

Use power words and urgency where sensible (e.g., "Premium", "Best-selling", 
"Eco-friendly"). Return your response by calling the GenerateListing tool 
with valid JSON."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                tools=tools,
                tool_choice={"type": "tool", "name": "GenerateListing"},
                messages=[{"role": "user", "content": user_msg}]
            )
            
            # Find tool_use block in response
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_use_block = block
                    break
            
            if not tool_use_block:
                raise ClaudeError("Claude did not call GenerateListing tool", 500)
            
            # Extract and validate tool input (already parsed JSON by SDK)
            input_dict = tool_use_block.input
            
            # Validate lengths
            if len(input_dict.get("title", "")) > 200:
                raise ClaudeError("Title exceeds 200 chars", 500)
            if len(input_dict.get("description", "")) > 300:
                raise ClaudeError("Description exceeds 300 chars", 500)
            
            # Validate bullets: must be list of 3-5 non-empty strings, each ≤100 chars
            bullets = input_dict.get("bullets")
            if not isinstance(bullets, list):
                raise ClaudeError("Bullets must be a list", 500)
            if len(bullets) < 3 or len(bullets) > 5:
                raise ClaudeError("Must have 3-5 bullets", 500)
            for i, bullet in enumerate(bullets):
                if not isinstance(bullet, str) or not bullet.strip():
                    raise ClaudeError(f"Bullet {i+1} must be a non-empty string", 500)
                if len(bullet) > 100:
                    raise ClaudeError(f"Bullet {i+1} exceeds 100 chars", 500)
            
            return {
                "title": input_dict["title"],
                "description": input_dict["description"],
                "bullets": input_dict["bullets"]
            }
        
        except ClaudeError:
            # Re-raise our own ClaudeError
            raise
        except APITimeoutError:
            raise ClaudeError("Claude API timeout", 504)
        except RateLimitError:
            raise ClaudeError("Claude rate limited", 429)
        except AuthenticationError:
            raise ClaudeError("Invalid Claude key", 401)
        except APIStatusError as e:
            raise ClaudeError(f"Claude API error: {e.message}", e.status_code or 500)
        except Exception as e:
            # Unexpected error
            raise ClaudeError(f"Unexpected error: {str(e)}", 500)
