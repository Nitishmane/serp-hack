# Amazon FBA Listing Generator

Generate SEO-optimized Amazon product titles, descriptions, and bullet points 
using SerpAPI competitive research and an LLM via OpenRouter (default: GLM 5.3 Flash).

## Demo

Input: "stainless steel water bottle"
Output: Listing with title, description, 3-5 bullets, extracted keywords, 
and competitor analysis.

## Setup

### Requirements
- Python 3.9+
- SerpAPI account (free tier: 100 searches/month)
- OpenRouter API key (https://openrouter.ai/keys)

### Install

1. Clone the repo:
   ```bash
   git clone <repo-url>
   cd serp_hack
   ```

2. Create virtual env:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` from `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

5. Run the app:
   ```bash
   python main.py
   ```

6. Open http://localhost:8000 in your browser

## API

**Endpoint:** `POST /generate`

**Request:**
```json
{
  "product_name": "stainless steel water bottle"
}
```

**Response (200):**
```json
{
  "title": "Stainless Steel Water Bottle 32oz Insulated...",
  "description": "Premium stainless steel keeps drinks...",
  "bullets": ["...", "...", "..."],
  "keywords_used": ["stainless steel", "water bottle", ...],
  "sources": {
    "search_queries": ["stainless steel water bottle"],
    "competitor_titles_found": ["...", "..."],
    "signal_count": 8
  }
}
```

## Testing

```bash
pytest tests/ -v
```

## Architecture

- **SerpAPI**: Google search results for keyword extraction
- **OpenRouter (GLM 5.3 Flash, tool-calling)**: Structured listing generation via OpenAI-compatible function calling. Set `OPENROUTER_MODEL` to swap in any other OpenRouter model.
- **FastAPI**: Async-ready REST API
- **Frontend**: Vanilla HTML/CSS/JS (no dependencies)

## Limitations

- Single user, no persistence
- SerpAPI free tier (100 searches/month); uses 1 query per request
- No authentication
- Demo-quality code (not production-ready)

## License

MIT
