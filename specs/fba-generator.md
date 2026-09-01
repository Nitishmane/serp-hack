# Amazon FBA Generator — Implementation Specification (Final)

**Deadline:** Sept 3, 2026 (2 days)  
**Scope:** Minimal, end-to-end working demo  
**Target:** Hackathon submission with public repo + README  

---

## 1. Architecture & File Layout

```
serp_hack/
├── README.md                          # Setup/run instructions
├── .env.example                       # Template for config (git-tracked)
├── .env                               # Actual secrets (gitignored)
├── .gitignore                         # Ignore .env, __pycache__, .venv
├── requirements.txt                   # Python dependencies (pinned versions)
├── main.py                            # FastAPI app entry point
├── static/
│   ├── index.html                     # Single-page frontend
│   ├── style.css                      # Minimal styling
│   └── app.js                         # Vanilla JS, no frameworks
├── src/
│   ├── __init__.py
│   ├── serp_client.py                 # SerpApi wrapper (sync requests)
│   ├── keyword_extractor.py           # Frequency-based extraction
│   ├── claude_generator.py            # Claude API wrapper + tool-use
│   └── schemas.py                     # Pydantic models for request/response
└── tests/
    ├── test_serp_client.py            # Mock SerpApi calls
    ├── test_keyword_extractor.py      # Keyword extraction sanity
    └── test_integration.py            # End-to-end mock flow
```

**Tech Stack:**
- **FastAPI** (lightweight, for demo)
- **Pydantic** (type safety, validation)
- **requests** (sync HTTP for SerpApi)
- **anthropic** (Claude SDK)
- **python-dotenv** (env config)
- **pytest** (basic tests)

---

## 2. Data Flow (High Level)

```
[User Input] 
    ↓ product_name (string, 1-200 chars)
[Frontend POST /generate]
    ↓
[FastAPI input validation]
    ↓ (fail → return 400)
[SerpApi: Google Search (1 query)]
    ↓ (fail → return 5xx)
[Keyword Extraction] 
    ↓ (filter stopwords, frequency sort, defensive handling of missing keys)
[Claude Tool-Use Call (structured output)]
    ↓ (force structured JSON response via tool schema)
[Return to Frontend]
    ↓
[Display Title, Description, Bullets, Keywords Used, Source Info]
```

**Request:** `POST /generate`
```json
{
  "product_name": "stainless steel water bottle"
}
```

**Response (Success 200):**
```json
{
  "title": "Stainless Steel Water Bottle 32oz Insulated Double-Wall Vacuum Flask...",
  "description": "Premium stainless steel construction keeps drinks hot/cold for 24 hours. Eco-friendly, BPA-free design perfect for fitness, outdoor, and office use.",
  "bullets": [
    "Double-wall vacuum insulation keeps drinks at temperature for 24 hours",
    "Lightweight, durable stainless steel with anti-slip grip",
    "Eco-friendly, BPA-free, food-grade materials"
  ],
  "keywords_used": ["stainless steel", "water bottle", "insulated", "double-wall", "vacuum", "32oz"],
  "sources": {
    "search_queries": ["stainless steel water bottle"],
    "competitor_titles_found": [
      "Stainless Steel Insulated Water Bottle",
      "Double Wall Vacuum Flask Bottle"
    ],
    "signal_count": 8
  }
}
```

**Response (Error 400):**
```json
{
  "error": "product_name required",
  "status_code": 400
}
```

**Response (Error 5xx):**
```json
{
  "error": "SerpApi timeout",
  "status_code": 504,
  "details": "Try again in 30 seconds"
}
```

---

## 3. SerpApi Integration (Reduced Scope)

### 3.1 Queries to Run

**Query 1: Google Search (main query only)**
- `q`: `product_name` (e.g., "stainless steel water bottle")
- `engine`: `google`
- `num`: `10` (top 10 results)
- Parse: organic results (titles + snippets), related searches (if present)
- **Do NOT parse** `people_also_ask` — too common to be missing; skip if absent

**Why reduce from 3 to 1 query?**
- SerpApi free tier: 100 searches/month
- 1 query × 100 = ~33 generate requests max before quota exhaustion
- 3 queries × 100 = ~11 requests (risks demo day)
- **Decision**: 1 Google search captures sufficient keyword signal for hackathon demo without quota risk

### 3.2 Implementation (serp_client.py)

```python
import requests
from typing import Optional

class SerpAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
    
    def search_google(self, query: str, num_results: int = 10) -> dict:
        """
        Fetch Google search results. Defensive: gracefully handles missing keys.
        
        Returns: {
            "organic_results": [{"title": "...", "snippet": "..."}, ...],
            "related_searches": ["...", ...] or [],
            "error": None
        }
        
        On failure: {
            "organic_results": [],
            "related_searches": [],
            "error": "SerpApi timeout"
        }
        """
        try:
            response = requests.get(
                self.base_url,
                params={
                    "q": query,
                    "engine": "google",
                    "num": num_results,
                    "api_key": self.api_key
                },
                timeout=10
            )
            
            if response.status_code == 429:
                return {"error": "rate_limited", "status_code": 429}
            elif response.status_code == 401:
                return {"error": "invalid_key", "status_code": 401}
            elif response.status_code >= 500:
                return {"error": "serp_api_error", "status_code": response.status_code}
            elif response.status_code != 200:
                return {"error": "serp_api_error", "status_code": response.status_code}
            
            data = response.json()
            
            # Defensive extraction: use .get() with defaults
            organic_results = data.get("organic_results", [])
            related_searches = data.get("related_searches", [])
            
            return {
                "organic_results": [
                    {"title": r.get("title", ""), "snippet": r.get("snippet", "")}
                    for r in organic_results
                ],
                "related_searches": [
                    s.get("query", "") for s in related_searches
                ],
                "error": None
            }
        
        except requests.Timeout:
            return {"error": "timeout", "status_code": 504}
        except requests.RequestException as e:
            return {"error": "network_error", "status_code": 503}
        except ValueError:
            # JSON decode error from response.json()
            return {"error": "SerpApi response invalid", "status_code": 500}
        except Exception as e:
            return {"error": f"unexpected_error: {str(e)}", "status_code": 500}
    
    def get_signals_for_product(self, product_name: str) -> dict:
        """
        Orchestrates Google search, returns all signals (sync, no await).
        """
        return self.search_google(product_name)
```

### 3.3 Error Handling

| Scenario | HTTP Status | Response Detail |
|----------|-------------|---|
| Timeout (>10s) | 504 | `"SerpApi timeout"` |
| Rate limit (429) | 429 | `"SerpApi rate limited"` |
| Invalid API key (401) | 401 | `"Invalid SerpApi key"` |
| Other network error | 503 | `"SerpApi unreachable"` |
| JSON parse error | 500 | `"SerpApi response invalid"` |

---

## 4. Keyword Extraction

### 4.1 Strategy (keyword_extractor.py)

Simple, no NLP:
1. Combine all text from SerpApi response:
   - Organic result titles
   - Organic result snippets
   - Related search phrases
2. Tokenize by whitespace and punctuation
3. Filter out stopwords (the, a, an, and, or, for, in, on, is, be, …)
4. Extract **1-grams** and **2-grams** (unigrams and bigrams; skip 3-grams for brevity)
5. Count frequency across all text
6. Rank by frequency (descending)
7. Return top ~10-15 keywords/phrases

### 4.2 Defensive Handling

```python
def extract_keywords(serp_data: dict, top_n: int = 15) -> list[str]:
    """
    Extract keywords from SerpApi response.
    Gracefully handles missing/empty keys: returns [] if no data.
    """
    all_text = []
    
    # Defensive: check if organic_results exists and is iterable
    if "organic_results" in serp_data and serp_data["organic_results"]:
        for result in serp_data["organic_results"]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            if title:
                all_text.append(title)
            if snippet:
                all_text.append(snippet)
    
    # Defensive: check if related_searches exists and is iterable
    if "related_searches" in serp_data and serp_data["related_searches"]:
        all_text.extend(serp_data["related_searches"])
    
    if not all_text:
        return []  # No crash; just return empty list
    
    # Tokenize, filter stopwords, extract n-grams, rank by frequency
    tokens = tokenize_and_filter(all_text)
    ngrams = extract_ngrams(tokens, n=[1, 2])
    freq_sorted = sort_by_frequency(ngrams)
    return freq_sorted[:top_n]
```

### 4.3 Example Output

```python
["stainless steel", "water bottle", "insulated", "double-wall", "BPA free", "32oz", ...]
```

---

## 5. Claude Integration (Tool-Use for Structured Output)

### 5.1 Why Tool-Use?

**Problem with raw JSON prompt**: Claude can emit markdown fences, preamble, or truncation. Parsing with `json.loads()` fails unreliably.

**Solution**: Use Claude's native **tool-use** (function calling) to force structured output. The model must emit valid JSON in the tool_use block; no parsing ambiguity.

### 5.2 System Prompt (claude_generator.py)

```
You are an expert Amazon product listing copywriter who specializes in 
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
with valid JSON.
```

### 5.3 Tool Definition (in messages API call)

Anthropic's `tools` parameter expects a flat list of tool objects with `name`, `description`, and `input_schema` at the top level. Do NOT wrap with `"type": "function"` or nest under a `"function"` key—that is OpenAI's format and will cause a validation error.

```python
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
```

### 5.4 Code Sketch (claude_generator.py)

```python
from anthropic import Anthropic, APITimeoutError, RateLimitError, AuthenticationError, APIStatusError
import json

class ClaudeGenerator:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
    
    def generate_listing(self, product_name: str, keywords: list[str]) -> dict:
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
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
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

class ClaudeError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
```

**Why `tool_choice={"type": "tool", "name": "GenerateListing"}`?**

Without forcing `tool_choice`, Claude may respond with plain text explanation instead of calling the tool—especially if it judges the tool call unnecessary. This makes the code unpredictably hit the `if not tool_use_block: raise ClaudeError(...)` path, breaking the feature. Forcing tool_choice ensures the model *must* call the tool, guaranteeing structured output suitable for a live demo.

---

## 6. FastAPI Endpoint & Error Handling

### 6.1 Endpoint Design (main.py)

```python
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

from src.schemas import GenerateRequest, GenerateResponse
from src.serp_client import SerpAPIClient
from src.keyword_extractor import extract_keywords
from src.claude_generator import ClaudeGenerator

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
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 6.2 Pydantic Schemas (schemas.py)

```python
from pydantic import BaseModel, Field

class GenerateRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)

class GenerateResponse(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=300)
    bullets: list[str]
    keywords_used: list[str]
    sources: dict
```

### 6.3 Failure Mode Matrix

| Failure | Status | Detail | Frontend Shows |
|---------|--------|--------|---|
| Empty product_name | 400 | `"product_name required"` | "Please enter a product name" |
| product_name > 200 chars | 400 | `"product_name too long"` | "Product name too long (max 200)" |
| SerpApi timeout | 504 | `"timeout"` | "Search took too long, try again" |
| SerpApi rate limit | 429 | `"rate_limited"` | "Rate limited, wait 1 min" |
| SerpApi invalid key | 401 | `"invalid_key"` | "Server misconfigured (dev error)" |
| Claude rate limit | 429 | `"Claude rate limited"` | "Generation busy, try again" |
| Claude invalid key | 401 | `"Invalid Claude key"` | "Server misconfigured (dev error)" |
| Claude timeout | 504 | `"Claude API timeout"` | "Generation took too long, try again" |
| Claude tool error | 500 | `"Claude did not call GenerateListing tool"` | "Generation failed, try again" |
| Network error | 503 | `"SerpApi unreachable"` | "Network error, check connection" |

---

## 7. Frontend (HTML/CSS/JS)

### 7.1 index.html (static/index.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amazon FBA Generator</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Amazon FBA Listing Generator</h1>
        <p class="subtitle">Enter your product name to generate SEO-optimized titles & descriptions</p>
        
        <form id="generatorForm">
            <input 
                type="text" 
                id="productName" 
                placeholder="e.g., stainless steel water bottle" 
                maxlength="200"
                required
            >
            <button type="submit" id="submitBtn">Generate</button>
        </form>
        
        <div id="loading" class="hidden">
            <p>Generating...</p>
        </div>
        
        <div id="error" class="hidden">
            <p class="error-message"></p>
        </div>
        
        <div id="results" class="hidden">
            <div class="result-item">
                <h2>Amazon Title</h2>
                <p id="resultTitle" class="copy-field"></p>
                <button class="copy-btn">Copy</button>
            </div>
            
            <div class="result-item">
                <h2>Description</h2>
                <p id="resultDescription" class="copy-field"></p>
                <button class="copy-btn">Copy</button>
            </div>
            
            <div class="result-item">
                <h2>Key Bullet Points</h2>
                <ul id="resultBullets"></ul>
            </div>
            
            <div class="result-item">
                <h2>Keywords Used</h2>
                <div id="resultKeywords" class="tags"></div>
            </div>
            
            <div class="result-item">
                <h2>Source Info</h2>
                <div id="resultSources"></div>
            </div>
        </div>
    </div>
    
    <script src="/static/app.js"></script>
</body>
</html>
```

### 7.2 app.js (static/app.js)

```javascript
document.getElementById('generatorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const productName = document.getElementById('productName').value.trim();
    if (!productName) return;
    
    show('loading');
    hide('error');
    hide('results');
    
    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_name: productName })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.detail || 'Unknown error');
            return;
        }
        
        displayResults(data);
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        hide('loading');
    }
});

function displayResults(data) {
    document.getElementById('resultTitle').textContent = data.title;
    document.getElementById('resultDescription').textContent = data.description;
    document.getElementById('resultBullets').innerHTML = 
        data.bullets.map(b => `<li>${b}</li>`).join('');
    document.getElementById('resultKeywords').innerHTML = 
        data.keywords_used.map(k => `<span class="tag">${k}</span>`).join('');
    
    const sourcesInfo = data.sources;
    const sourcesHTML = `
        <p><strong>Competitors found:</strong> ${sourcesInfo.competitor_titles_found.length}</p>
        <p><strong>Total signals:</strong> ${sourcesInfo.signal_count}</p>
    `;
    document.getElementById('resultSources').innerHTML = sourcesHTML;
    
    show('results');
}

function showError(msg) {
    document.querySelector('#error .error-message').textContent = msg;
    show('error');
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

// Copy-to-clipboard
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const field = btn.previousElementSibling;
        navigator.clipboard.writeText(field.textContent);
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
});
```

### 7.3 style.css (static/style.css)

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f5f5;
    color: #333;
}
.container { max-width: 700px; margin: 40px auto; padding: 20px; }
h1 { font-size: 28px; margin-bottom: 10px; color: #232f3e; }
h2 { font-size: 18px; margin-bottom: 10px; }
.subtitle { color: #666; margin-bottom: 30px; }
form { display: flex; gap: 10px; margin-bottom: 30px; }
input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
button { padding: 10px 20px; background: #FF9900; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
button:hover { background: #e88d00; }
.hidden { display: none; }
.loading { color: #666; font-style: italic; }
#error { background: #fee; padding: 15px; border-radius: 4px; color: #c33; margin-bottom: 20px; border-left: 4px solid #c33; }
.result-item { background: white; padding: 20px; margin-bottom: 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.copy-field { margin-bottom: 10px; padding: 10px; background: #f9f9f9; border-radius: 3px; word-wrap: break-word; }
.copy-btn { padding: 5px 10px; font-size: 12px; }
#resultBullets { margin-left: 20px; }
#resultBullets li { margin-bottom: 8px; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { background: #e0e0e0; padding: 4px 8px; border-radius: 3px; font-size: 12px; }
```

---

## 8. Environment & Dependencies

### 8.1 requirements.txt

```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0
anthropic>=0.40.0
requests==2.31.0
pytest==7.4.3
```

### 8.2 .env.example (git-tracked)

```
SERPAPI_API_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 8.3 .gitignore

```
.env
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/
dist/
build/
.DS_Store
```

---

## 9. Testing

### 9.1 Scope

Minimal sanity tests; mocked dependencies; no heavy coverage.

### 9.2 Test Cases

**test_serp_client.py:**
```python
def test_google_search_returns_valid_data():
    # Mock requests.get, verify organic_results and related_searches parsing
    
def test_google_search_handles_rate_limit():
    # Mock 429 response, verify error dict returned
    
def test_google_search_handles_missing_keys():
    # Mock response without "related_searches", verify [] returned (no crash)
    
def test_google_search_handles_timeout():
    # Mock timeout, verify error dict returned
```

**test_keyword_extractor.py:**
```python
def test_extract_keywords_filters_stopwords():
    # Input: SERP data with "the", "and", etc.; verify filtered
    
def test_extract_keywords_returns_top_n():
    # Verify top 15 keywords returned, sorted by frequency
    
def test_extract_keywords_handles_empty_data():
    # Input: empty dict/no organic results, verify [] returned (no crash)
```

**test_integration.py:**
```python
def test_endpoint_generate_success():
    # Mock SerpApi + Claude, POST /generate, verify 200 response with all fields
    
def test_endpoint_generate_invalid_input():
    # POST /generate with empty product_name, verify 400
    
def test_endpoint_generate_serp_error():
    # Mock SerpApi returning error, verify 5xx returned
    
def test_endpoint_generate_claude_error():
    # Mock Claude timeout, verify 504 returned
```

### 9.3 Run Tests

```bash
pytest tests/ -v
```

---

## 10. README.md

```markdown
# Amazon FBA Listing Generator

Generate SEO-optimized Amazon product titles, descriptions, and bullet points 
using SerpAPI competitive research and Claude AI.

## Demo

Input: "stainless steel water bottle"
Output: Listing with title, description, 3-5 bullets, extracted keywords, 
and competitor analysis.

## Setup

### Requirements
- Python 3.9+
- SerpAPI account (free tier: 100 searches/month)
- Anthropic Claude API key

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
- **Claude AI (Tool-Use)**: Structured listing generation via native tool-calling
- **FastAPI**: Async-ready REST API
- **Frontend**: Vanilla HTML/CSS/JS (no dependencies)

## Limitations

- Single user, no persistence
- SerpAPI free tier (100 searches/month); use 1 query per request
- No authentication
- Demo-quality code (not production-ready)

## License

MIT
```

---

## 11. Implementation Order & Checkpoints

### Day 1 (Sept 1)
1. **Project setup**: Create structure, requirements.txt, .env.example, .gitignore
2. **SerpApi client**: Implement sync `serp_client.py`, test with real API (use mocks for pytest)
3. **Keyword extractor**: Implement `keyword_extractor.py`, test defensive handling
4. **Claude generator**: Implement tool-use in `claude_generator.py`, test with real API

### Day 1 → Day 2 (Morning)
5. **FastAPI endpoint**: Wire components in `main.py`, run full flow end-to-end
6. **Frontend**: HTML/CSS/JS, test in browser

### Day 2 (Afternoon)
7. **Error handling**: Audit failure modes, verify all error responses work
8. **Tests**: 5-6 pytest tests with mocks, verify all pass
9. **Documentation**: README, .env.example, inline comments
10. **Final check**: Repo is public, instructions work end-to-end

### If Behind Schedule
- Cut: Test coverage (verify manually)
- Cut: Keyword extraction edge cases (use product_name as fallback)
- Reduce: Bullet points to 2 (if time pressure)

---

## 12. Acceptance Criteria (Concrete & Checkable)

**Endpoint Behavior:**
- [ ] `GET /` serves static HTML without error (200)
- [ ] `POST /generate` with valid product_name (1-200 chars) returns 200 with all required fields
- [ ] `POST /generate` with empty product_name returns 400
- [ ] `POST /generate` with product_name > 200 chars returns 400
- [ ] Response title is ≤ 200 characters
- [ ] Response description is ≤ 300 characters
- [ ] Response has 3-5 bullet points (non-empty strings)
- [ ] Response keywords_used is a non-empty list
- [ ] Response sources contains search_queries, competitor_titles_found, signal_count
- [ ] `POST /generate` with SerpAPI failure returns 5xx (not 200)
- [ ] `POST /generate` with Claude failure returns 5xx (not 200)

**Frontend Behavior:**
- [ ] Form submits without JS errors (console clean)
- [ ] Loading spinner shows while generating
- [ ] Results div displays title, description, bullets, keywords (all visible)
- [ ] Copy buttons work (clipboard functionality)
- [ ] Error messages display on API failure
- [ ] Form validates max 200 chars client-side

**Code Quality:**
- [ ] No API keys committed to git (verify .gitignore works)
- [ ] All imports resolve (pip install works)
- [ ] No syntax errors (python -m py_compile *.py)
- [ ] Model ID is "claude-sonnet-4-5" (not deprecated model)

**Tests:**
- [ ] `pytest tests/test_serp_client.py` passes (all 4 tests)
- [ ] `pytest tests/test_keyword_extractor.py` passes (all 3 tests)
- [ ] `pytest tests/test_integration.py` passes (all 4 tests)
- [ ] All mocked (no real API calls during pytest)

**Documentation:**
- [ ] README.md exists and explains setup/run/API
- [ ] .env.example exists with SERPAPI_API_KEY, ANTHROPIC_API_KEY
- [ ] .gitignore blocks .env, __pycache__, .venv
- [ ] Repo is public (GitHub/GitLab)

**Performance:**
- [ ] `/generate` responds within 15 seconds (typical: 2-5s)
- [ ] No blocking database calls or excessive I/O
- [ ] Timeout handling verified (SerpAPI + Claude each timeout gracefully)

---

## 13. Justifications for Design Choices

| Choice | Why |
|--------|-----|
| **1 SerpAPI query (not 3)** | Free tier = 100/month; 3 queries = 33 requests max (risky for demo day). 1 query preserves quota for testing/judging. |
| **Sync client (not async)** | Demo scope; 1 request at a time is fine. Avoids complexity of httpx.AsyncClient + event loop management. |
| **Claude tool-use (not raw JSON)** | Native structured output; no parsing fragility. Guaranteed valid JSON in tool_use block. |
| **Defensive keyword extraction** | SerpAPI doesn't reliably include all fields. `.get()` with defaults prevents crashes on partial responses. |
| **Vanilla JS frontend** | No npm/build step; single .html file; easier for judges to run locally. |
| **Pydantic schemas** | Type safety, validation, auto-generated OpenAPI docs. |
| **Simple frequency-based keywords** | No NLP/spaCy needed; easy to understand and debug. Sufficient signal for demo. |

---

**End of Spec**
