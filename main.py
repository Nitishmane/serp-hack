from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

from src.schemas import GenerateRequest, GenerateResponse
from src.serp_client import SerpAPIClient
from src.keyword_extractor import extract_keywords
from src.llm_generator import ListingGenerator, LLMError

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")

if not SERPAPI_API_KEY or not OPENROUTER_API_KEY:
    raise RuntimeError("Missing API keys (set them in .env locally or as Vercel env vars)")

# Absolute paths so static serving works both locally and inside Vercel's
# serverless filesystem (where the working directory is not the project root).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

serp_client = SerpAPIClient(SERPAPI_API_KEY)
llm_gen = ListingGenerator(OPENROUTER_API_KEY, OPENROUTER_MODEL)


@app.get("/")
def read_root():
    """Serve index.html"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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
        
        # 3. Generate with the LLM (via tool-use over OpenRouter)
        listing = llm_gen.generate_listing(product_name, keywords)
        
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
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
