import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import os

# Ensure env vars are set before any imports
os.environ.setdefault("SERPAPI_API_KEY", "test_key")
os.environ.setdefault("OPENROUTER_API_KEY", "test_key")

# Import app once at module level
from main import app


def _signals(**overrides):
    """A merged multi-engine signals dict as returned by get_signals_for_product."""
    base = {
        "organic_results": [
            {"title": "Premium Water Bottle", "snippet": "Insulated stainless steel"},
            {"title": "Best Water Bottle", "snippet": "Keep drinks cold"},
        ],
        "related_searches": ["insulated water bottle", "stainless steel bottle"],
        "related_questions": ["is stainless steel safe?"],
        "amazon_products": [
            {"title": "Hydro Bottle 32oz", "price": 24.99, "price_str": "$24.99", "rating": 4.6, "reviews": 1200},
            {"title": "ColdKeep Vacuum Flask", "price": 19.99, "price_str": "$19.99", "rating": 4.4, "reviews": 800},
        ],
        "autocomplete": ["water bottle insulated", "water bottle 32oz"],
        "price_stats": {"min": 19.99, "max": 24.99, "median": 22.49, "count": 2},
        "engine_errors": {"google": None, "amazon": None, "autocomplete": None},
        "error": None,
    }
    base.update(overrides)
    return base


def _listing(**overrides):
    base = {
        "title": "Premium Stainless Steel Water Bottle 32oz",
        "description": "Keep your beverages at the perfect temperature all day long.",
        "bullets": ["Double-wall insulation", "Eco-friendly", "Durable", "Leakproof"],
        "suggested_price": "$21.99",
        "positioning": "Positioned as the durable, leakproof mid-price pick versus bulkier rivals.",
    }
    base.update(overrides)
    return base


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
    with patch('main.serp_client.get_signals_for_product') as mock_signals:
        with patch.object(__import__('main').llm_gen, 'generate_listing') as mock_generate:
            mock_signals.return_value = _signals()
            mock_generate.return_value = _listing()

            response = client.post("/generate", json={"product_name": "water bottle"})

            assert response.status_code == 200
            data = response.json()

            for key in ("title", "description", "bullets", "keywords_used", "sources",
                        "suggested_price", "positioning"):
                assert key in data

            assert data["title"] == "Premium Stainless Steel Water Bottle 32oz"
            assert data["suggested_price"] == "$21.99"
            assert data["positioning"]
            assert len(data["bullets"]) == 4
            # Richer sources from the multi-engine research
            assert "amazon_competitors" in data["sources"]
            assert len(data["sources"]["amazon_competitors"]) == 2
            assert data["sources"]["price_stats"]["median"] == 22.49
            assert "amazon" in data["sources"]["engines_used"]


def test_generate_passes_context_to_llm(client):
    """The competitor research should be forwarded to the generator as context."""
    with patch('main.serp_client.get_signals_for_product') as mock_signals:
        with patch.object(__import__('main').llm_gen, 'generate_listing') as mock_generate:
            mock_signals.return_value = _signals()
            mock_generate.return_value = _listing()

            client.post("/generate", json={"product_name": "water bottle"})

            args, kwargs = mock_generate.call_args
            context = kwargs.get("context") or args[2]
            assert context["price_stats"]["median"] == 22.49
            assert "Hydro Bottle 32oz" in context["competitor_titles"]


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


@patch('main.serp_client.get_signals_for_product')
def test_generate_with_serp_error_429(mock_signals, client):
    """Test POST /generate with all engines failing (rate limited) returns 429"""
    mock_signals.return_value = {
        "error": "rate_limited",
        "status_code": 429,
        "organic_results": [],
        "related_searches": [],
        "amazon_products": [],
        "autocomplete": [],
    }

    response = client.post("/generate", json={"product_name": "test product"})

    assert response.status_code == 429


def test_generate_with_llm_error(client):
    """Test POST /generate with mocked LLM raising an error returns 5xx"""
    with patch('main.serp_client.get_signals_for_product') as mock_signals:
        with patch.object(__import__('main').llm_gen, 'generate_listing') as mock_generate:
            mock_signals.return_value = _signals()

            from src.llm_generator import LLMError
            mock_generate.side_effect = LLMError("API error", 500)

            response = client.post("/generate", json={"product_name": "test product"})

            assert response.status_code >= 500


def test_full_flow_success(client):
    """Test successful end-to-end generation flow through HTTP"""
    with patch('main.serp_client.get_signals_for_product') as mock_signals:
        with patch.object(__import__('main').llm_gen, 'generate_listing') as mock_generate:
            mock_signals.return_value = _signals()
            mock_generate.return_value = _listing()

            response = client.post("/generate", json={"product_name": "water bottle"})

            assert response.status_code == 200
            data = response.json()
            assert data["title"]
            assert data["description"]
            assert len(data["bullets"]) > 0
            assert len(data["keywords_used"]) > 0
            assert "search_queries" in data["sources"]
