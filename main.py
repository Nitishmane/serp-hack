from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

from src.schemas import GenerateRequest, GenerateResponse
from src.serp_client import SerpAPIClient
from src.keyword_extractor import extract_keywords
from src.claude_generator import ClaudeGenerator, ClaudeError

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not SERPAPI_API_KEY or not ANTHROPIC_API_KEY:
    raise RuntimeError("Missing API keys in .env")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

serp_client = SerpAPIClient(SERPAPI_API_KEY)
claude_gen = ClaudeGenerator(ANTHROPIC_API_KEY)


@app.get("/")
def read_root():
    """Serve index.html"""
    return FileResponse("static/index.html")


@app.post("/generate")
def generate(request: GenerateRequest) -> GenerateResponse:
    """
    Generate SEO-optimized Amazon listing.
    Synchronous endpoint (no async needed for demo).
    """
    product_name = request.product_name.strip()
    
    # Validation
    if not product_name:
        raise HTTPException(status_code=400, detail="product_name required")
    if len(product_name) > 200:
        raise HTTPException(status_code=400, detail="product_name too long (max 200)")
    
    try:
        # 1. Fetch SerpApi data
        serp_result = serp_client.get_signals_for_product(product_name)
        if serp_result.get("error"):
            error_code = serp_result.get("status_code", 500)
            raise HTTPException(
                status_code=error_code,
                detail=serp_result["error"]
            )
        
        # 2. Extract keywords (defensively handles empty/missing keys)
        keywords = extract_keywords(serp_result)
        if not keywords:
            # Fallback: use product_name itself if extraction fails
            keywords = [product_name]
        
        # 3. Generate with Claude (via tool-use)
        listing = claude_gen.generate_listing(product_name, keywords)
        
        # 4. Extract source info for response
        organic_count = len(serp_result.get("organic_results", []))
        competitor_titles = [
            r.get("title", "") for r in serp_result.get("organic_results", [])[:3]
        ]
        
        # 5. Return response
        return GenerateResponse(
            title=listing["title"],
            description=listing["description"],
            bullets=listing["bullets"],
            keywords_used=keywords,
            sources={
                "search_queries": [product_name],
                "competitor_titles_found": competitor_titles,
                "signal_count": organic_count
            }
        )
    
    except HTTPException:
        raise
    except ClaudeError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
