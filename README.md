# Amazon FBA Listing Generator

Generate SEO-optimized Amazon product titles, descriptions, bullet points, a
suggested price, and a competitive positioning angle — built from **live
multi-engine competitor research** (SerpApi) and an LLM via **OpenRouter**
(default: GLM 5.3 Flash).

**Live demo:** https://serp-hack.vercel.app

## Demo

Input: `stainless steel water bottle`

Output: a full listing (title, description, 4–5 bullets), a **suggested price**
benchmarked against real Amazon listings, a **positioning angle** vs named
competitors, the extracted keywords, and a competitor/price/rating panel.

## How it works

```
product name
   ↓
┌─ SerpApi (3 engines, run in parallel) ────────────────┐
│  • Google        → organic titles, related, PAA       │
│  • Amazon        → competitor titles, prices, ratings │
│  • Autocomplete  → long-tail buyer phrases            │
└───────────────────────────────────────────────────────┘
   ↓ frequency-based keyword extraction + price stats
GLM 5.3 Flash (OpenRouter, forced tool-calling)
   ↓ structured JSON: title, description, bullets, price, positioning
FastAPI response → vanilla JS frontend
```

The three SerpApi engines run concurrently, so the extra research costs roughly
the wall-time of a single call. The flow is resilient: if one or two engines
fail, it proceeds with whatever came back and only errors if all three fail.

## Setup

### Requirements
- Python 3.9+
- [SerpApi](https://serpapi.com) account (each generation uses 3 searches)
- [OpenRouter](https://openrouter.ai/keys) API key

### Install

1. Clone and enter the repo:
   ```bash
   git clone <repo-url>
   cd serp-hack
   ```

2. Create a virtual env and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create `.env` from the template and add your keys:
   ```bash
   cp .env.example .env
   # edit .env:
   #   SERPAPI_API_KEY=...
   #   OPENROUTER_API_KEY=...
   #   OPENROUTER_MODEL=z-ai/glm-5.3-flash   # optional; any OpenRouter model slug
   ```

4. Run:
   ```bash
   python main.py
   ```
   Open http://localhost:8000

## API

**Endpoint:** `POST /generate`

**Request:**
```json
{ "product_name": "stainless steel water bottle" }
```

**Response (200):**
```json
{
  "title": "Premium Stainless Steel Water Bottle 32oz Insulated...",
  "description": "Double-wall vacuum insulation keeps drinks cold for 24 hours...",
  "bullets": ["...", "...", "..."],
  "suggested_price": "$21.99",
  "positioning": "Positioned as the durable, leakproof mid-price pick vs bulkier rivals.",
  "keywords_used": ["stainless steel", "water bottle", "insulated", "..."],
  "sources": {
    "search_queries": ["stainless steel water bottle"],
    "engines_used": ["google", "amazon", "autocomplete"],
    "competitor_titles_found": ["...", "..."],
    "amazon_competitors": [
      { "title": "Owala FreeSip 32oz", "price": "$29.99", "rating": 4.6, "reviews": 136000 }
    ],
    "price_stats": { "min": 7.98, "max": 50.0, "median": 22.97, "count": 48 },
    "autocomplete": ["stainless steel water bottle with straw", "..."],
    "signal_count": 64
  }
}
```

Errors return the appropriate 4xx/5xx status with a `detail` message
(e.g. `400` for empty input, `429` when SerpApi/OpenRouter is rate limited).

## Testing

```bash
pytest tests/ -v
```

All tests are mocked — no real API calls.

## Architecture

- **SerpApi (3 engines)**: Google + Amazon + Google Autocomplete, fetched
  concurrently, for competitor titles, live prices/ratings, and buyer search terms.
- **Keyword extraction**: pure-Python frequency ranking of unigrams + bigrams
  across all engine results (no heavy NLP).
- **OpenRouter (GLM 5.3 Flash)**: structured output via OpenAI-compatible
  forced tool-calling. GLM is a reasoning model, so `reasoning.effort=low` +
  a generous `max_tokens` keep it fast and prevent truncated tool arguments.
  Set `OPENROUTER_MODEL` to swap in any other OpenRouter model.
- **FastAPI**: single `POST /generate` endpoint.
- **Frontend**: dependency-free HTML/CSS/JS.

## Deployment (Vercel)

Deployed as a Python serverless function via `vercel.json` (`@vercel/python`).
Set `SERPAPI_API_KEY`, `OPENROUTER_API_KEY`, and (optionally) `OPENROUTER_MODEL`
in the Vercel project's Environment Variables — the `.env` file is never uploaded.

## Limitations

- Single user, no persistence or authentication
- Each generation uses 3 SerpApi searches (mind your plan's monthly quota)
- Latency ~5–20s (GLM reasoning + live research)
- Demo-quality code (not production-hardened)

## License

MIT
