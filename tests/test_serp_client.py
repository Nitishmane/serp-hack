import pytest
from unittest.mock import patch, MagicMock
from src.serp_client import SerpAPIClient


@patch('src.serp_client.requests.get')
def test_google_search_returns_valid_data(mock_get):
    """Test that SerpAPI client correctly parses valid response"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "organic_results": [
            {"title": "Test Title 1", "snippet": "Test snippet 1"},
            {"title": "Test Title 2", "snippet": "Test snippet 2"}
        ],
        "related_searches": [
            {"query": "related search 1"},
            {"query": "related search 2"}
        ]
    }
    mock_get.return_value = mock_response
    
    client = SerpAPIClient("test_key")
    result = client.search_google("test query")
    
    assert result["error"] is None
    assert len(result["organic_results"]) == 2
    assert result["organic_results"][0]["title"] == "Test Title 1"
    assert len(result["related_searches"]) == 2
    assert result["related_searches"][0] == "related search 1"


@patch('src.serp_client.requests.get')
def test_google_search_handles_rate_limit(mock_get):
    """Test that 429 rate limit is handled gracefully"""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_get.return_value = mock_response
    
    client = SerpAPIClient("test_key")
    result = client.search_google("test query")
    
    assert result["error"] == "rate_limited"
    assert result["status_code"] == 429
    assert result["organic_results"] == []


@patch('src.serp_client.requests.get')
def test_google_search_handles_missing_keys(mock_get):
    """Test defensive handling when related_searches is missing"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "organic_results": [
            {"title": "Test Title", "snippet": "Test snippet"}
        ]
        # Note: no "related_searches" key
    }
    mock_get.return_value = mock_response
    
    client = SerpAPIClient("test_key")
    result = client.search_google("test query")
    
    assert result["error"] is None
    assert len(result["organic_results"]) == 1
    assert result["related_searches"] == []  # Should be empty, not crash


@patch('src.serp_client.requests.get')
def test_google_search_handles_timeout(mock_get):
    """Test that timeout is handled gracefully"""
    import requests
    mock_get.side_effect = requests.Timeout()
    
    client = SerpAPIClient("test_key")
    result = client.search_google("test query")
    
    assert result["error"] == "timeout"
    assert result["status_code"] == 504
    assert result["organic_results"] == []
