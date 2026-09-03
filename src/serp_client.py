import requests
from concurrent.futures import ThreadPoolExecutor


class SerpAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"

    def _get(self, params: dict):
        """
        Low-level SerpApi GET. Returns (data, error, status_code).
        data is None on failure; error is None on success.
        """
        try:
            response = requests.get(
                self.base_url,
                params={**params, "api_key": self.api_key},
                timeout=10,
            )
            if response.status_code == 429:
                return None, "rate_limited", 429
            elif response.status_code == 401:
                return None, "invalid_key", 401
            elif response.status_code != 200:
                return None, "serp_api_error", response.status_code
            return response.json(), None, 200
        except requests.Timeout:
            return None, "timeout", 504
        except requests.RequestException:
            return None, "network_error", 503
        except ValueError:
            return None, "invalid_response", 500
        except Exception as e:
            return None, f"unexpected_error: {str(e)}", 500

    def search_google(self, query: str, num_results: int = 10) -> dict:
        """Google Search: organic titles/snippets, related searches, people-also-ask."""
        data, error, status = self._get({"q": query, "engine": "google", "num": num_results})
        if error:
            return {"error": error, "status_code": status,
                    "organic_results": [], "related_searches": [], "related_questions": []}

        organic = data.get("organic_results", []) or []
        related = data.get("related_searches", []) or []
        paa = data.get("related_questions", []) or []
        return {
            "organic_results": [
                {"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in organic
            ],
            "related_searches": [s.get("query", "") for s in related if s.get("query")],
            "related_questions": [q.get("question", "") for q in paa if q.get("question")],
            "error": None,
        }

    def search_amazon(self, query: str) -> dict:
        """Amazon Search: real on-platform competitor products with price, rating, reviews."""
        data, error, status = self._get({"engine": "amazon", "k": query, "amazon_domain": "amazon.com"})
        if error:
            return {"error": error, "status_code": status, "products": []}

        organic = data.get("organic_results", []) or []
        products = []
        for r in organic:
            title = r.get("title", "")
            if not title:
                continue
            price = r.get("extracted_price")
            products.append({
                "title": title,
                "price": price if isinstance(price, (int, float)) else None,
                "price_str": r.get("price") or (f"${price}" if isinstance(price, (int, float)) else None),
                "rating": r.get("rating"),
                "reviews": r.get("reviews"),
            })
        return {"products": products, "error": None}

    def search_autocomplete(self, query: str) -> dict:
        """Google Autocomplete: long-tail phrases buyers actually type."""
        data, error, status = self._get({"engine": "google_autocomplete", "q": query})
        if error:
            return {"error": error, "status_code": status, "suggestions": []}

        suggestions = data.get("suggestions", []) or []
        return {"suggestions": [s.get("value", "") for s in suggestions if s.get("value")], "error": None}

    @staticmethod
    def _price_stats(products: list) -> dict | None:
        prices = sorted(p["price"] for p in products if isinstance(p.get("price"), (int, float)))
        if not prices:
            return None
        n = len(prices)
        median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
        return {
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "median": round(median, 2),
            "count": n,
        }

    def get_signals_for_product(self, product_name: str) -> dict:
        """
        Run all three engines concurrently and merge into a single signals dict.
        Resilient: proceeds on partial failure, only errors if EVERY engine fails.
        Keeps top-level organic_results/related_searches for backward compatibility.
        """
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_google = ex.submit(self.search_google, product_name)
            f_amazon = ex.submit(self.search_amazon, product_name)
            f_auto = ex.submit(self.search_autocomplete, product_name)
            google, amazon, auto = f_google.result(), f_amazon.result(), f_auto.result()

        products = amazon.get("products", [])
        result = {
            "organic_results": google.get("organic_results", []),
            "related_searches": google.get("related_searches", []),
            "related_questions": google.get("related_questions", []),
            "amazon_products": products,
            "autocomplete": auto.get("suggestions", []),
            "price_stats": self._price_stats(products),
            "engine_errors": {
                "google": google.get("error"),
                "amazon": amazon.get("error"),
                "autocomplete": auto.get("error"),
            },
        }

        # Only a hard failure if all three engines failed (typically bad key / rate limit).
        if google.get("error") and amazon.get("error") and auto.get("error"):
            result["error"] = google.get("error")
            result["status_code"] = google.get("status_code", 502)
        else:
            result["error"] = None
        return result
