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
                return {"error": "rate_limited", "status_code": 429, "organic_results": [], "related_searches": []}
            elif response.status_code == 401:
                return {"error": "invalid_key", "status_code": 401, "organic_results": [], "related_searches": []}
            elif response.status_code >= 500:
                return {"error": "serp_api_error", "status_code": response.status_code, "organic_results": [], "related_searches": []}
            elif response.status_code != 200:
                return {"error": "serp_api_error", "status_code": response.status_code, "organic_results": [], "related_searches": []}
            
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
            return {"error": "timeout", "status_code": 504, "organic_results": [], "related_searches": []}
        except requests.RequestException as e:
            return {"error": "network_error", "status_code": 503, "organic_results": [], "related_searches": []}
        except ValueError:
            # JSON decode error from response.json()
            return {"error": "SerpApi response invalid", "status_code": 500, "organic_results": [], "related_searches": []}
        except Exception as e:
            return {"error": f"unexpected_error: {str(e)}", "status_code": 500, "organic_results": [], "related_searches": []}
    
    def get_signals_for_product(self, product_name: str) -> dict:
        """
        Orchestrates Google search, returns all signals (sync, no await).
        """
        return self.search_google(product_name)
