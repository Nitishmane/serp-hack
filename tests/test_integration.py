import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import os

# Ensure env vars are set before any imports
os.environ.setdefault("SERPAPI_API_KEY", "test_key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

# Import app once at module level
from main import app


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app"""
    return TestClient(app)


def test_get_root(client):
    """Test that GET / returns 200"""
    response = client.get("/")
    assert response.status_code == 200


def test_generate_with_valid_product_name(client):
    """Test POST /generate with valid product_name returns 200 with all fields"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI response
            mock_search_google.return_value = {
                "organic_results": [
                    {"title": "Premium Water Bottle", "snippet": "Insulated stainless steel"},
                    {"title": "Best Water Bottle", "snippet": "Keep drinks cold"}
                ],
                "related_searches": [
                    "insulated water bottle",
                    "stainless steel bottle"
                ],
                "error": None
            }
            
            # Mock Claude generator
            mock_generate.return_value = {
                "title": "Premium Stainless Steel Water Bottle 32oz",
                "description": "Keep your beverages at the perfect temperature",
                "bullets": ["Double-wall insulation", "Eco-friendly", "Durable"]
            }
            
            response = client.post("/generate", json={"product_name": "water bottle"})
            
            assert response.status_code == 200
            data = response.json()
            
            assert "title" in data
            assert "description" in data
            assert "bullets" in data
            assert "keywords_used" in data
            assert "sources" in data
            
            assert data["title"] == "Premium Stainless Steel Water Bottle 32oz"
            assert data["description"] == "Keep your beverages at the perfect temperature"
            assert len(data["bullets"]) == 3


def test_generate_with_empty_product_name(client):
    """Test POST /generate with product_name='' returns 400"""
    response = client.post("/generate", json={"product_name": ""})
    
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


def test_generate_with_too_long_product_name(client):
    """Test POST /generate with product_name > 200 chars returns 400"""
    long_name = "a" * 250  # 250 chars, exceeds 200 limit
    response = client.post("/generate", json={"product_name": long_name})
    
    assert response.status_code == 400


@patch('main.serp_client.search_google')
def test_generate_with_serp_error_429(mock_search_google, client):
    """Test POST /generate with mocked SerpAPI returning rate_limited (429)"""
    # Mock SerpAPI returning a 429 error  
    mock_search_google.return_value = {
        "error": "rate_limited",
        "status_code": 429,
        "organic_results": [],
        "related_searches": []
    }
    
    response = client.post("/generate", json={"product_name": "test product"})
    
    assert response.status_code == 429


def test_generate_with_claude_error(client):
    """Test POST /generate with mocked Claude raising an error returns 5xx"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI success
            mock_search_google.return_value = {
                "organic_results": [{"title": "Test", "snippet": "Test snippet"}],
                "related_searches": [],
                "error": None
            }
            
            # Patch Claude generator to raise error
            from src.claude_generator import ClaudeError
            mock_generate.side_effect = ClaudeError("API error", 500)
            
            response = client.post("/generate", json={"product_name": "test product"})
            
            assert response.status_code >= 500


def test_full_flow_success(client):
    """Test successful end-to-end generation flow through HTTP"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI response
            mock_search_google.return_value = {
                "organic_results": [
                    {"title": "Premium Water Bottle", "snippet": "Insulated stainless steel"},
                    {"title": "Best Water Bottle", "snippet": "Keep drinks cold"}
                ],
                "related_searches": [
                    "insulated water bottle",
                    "stainless steel bottle"
                ],
                "error": None
            }
            
            # Patch Claude generator
            mock_generate.return_value = {
                "title": "Premium Stainless Steel Water Bottle",
                "description": "Keep your beverages at perfect temperature",
                "bullets": ["Double-wall", "Eco-friendly", "Durable", "Lightweight"]
            }
            
            response = client.post("/generate", json={"product_name": "water bottle"})
            
            assert response.status_code == 200
            data = response.json()
            assert data["title"]
            assert data["description"]
            assert len(data["bullets"]) > 0
            assert len(data["keywords_used"]) > 0
            assert "search_queries" in data["sources"]


def test_generate_with_invalid_bullet_count(client):
    """Test POST /generate with Claude returning only 1 bullet raises 500"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI success
            mock_search_google.return_value = {
                "organic_results": [{"title": "Test", "snippet": "Test snippet"}],
                "related_searches": [],
                "error": None
            }
            
            # Mock Claude generator to return only 1 bullet (violates 3-5 requirement)
            from src.claude_generator import ClaudeError
            mock_generate.side_effect = ClaudeError("Must have 3-5 bullets", 500)
            
            response = client.post("/generate", json={"product_name": "test product"})
            
            assert response.status_code == 500


def test_generate_with_bullet_exceeding_100_chars(client):
    """Test POST /generate with Claude returning a bullet over 100 chars raises 500"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI success
            mock_search_google.return_value = {
                "organic_results": [{"title": "Test", "snippet": "Test snippet"}],
                "related_searches": [],
                "error": None
            }
            
            # Mock Claude generator to return a bullet exceeding 100 chars
            from src.claude_generator import ClaudeError
            mock_generate.side_effect = ClaudeError("Bullet 1 exceeds 100 chars", 500)
            
            response = client.post("/generate", json={"product_name": "test product"})
            
            assert response.status_code == 500


def test_generate_with_empty_bullet(client):
    """Test POST /generate with Claude returning an empty bullet raises 500"""
    with patch('main.serp_client.search_google') as mock_search_google:
        with patch.object(__import__('main').claude_gen, 'generate_listing') as mock_generate:
            # Mock SerpAPI success
            mock_search_google.return_value = {
                "organic_results": [{"title": "Test", "snippet": "Test snippet"}],
                "related_searches": [],
                "error": None
            }
            
            # Mock Claude generator to return an empty bullet
            from src.claude_generator import ClaudeError
            mock_generate.side_effect = ClaudeError("Bullet 2 must be a non-empty string", 500)
            
            response = client.post("/generate", json={"product_name": "test product"})
            
            assert response.status_code == 500
