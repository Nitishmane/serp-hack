import pytest
from src.keyword_extractor import extract_keywords, tokenize_and_filter, extract_ngrams


def test_extract_keywords_filters_stopwords():
    """Test that stopwords like 'the', 'and' are filtered out"""
    serp_data = {
        "organic_results": [
            {"title": "The best water bottle and thermal insulator", "snippet": "Keep drinks hot or cold"},
            {"title": "Stainless steel bottle", "snippet": ""}
        ],
        "related_searches": []
    }
    
    keywords = extract_keywords(serp_data, top_n=10)
    
    # Should have keywords but not stopwords like 'the', 'and', 'or'
    keywords_lower = [k.lower() for k in keywords]
    assert "the" not in keywords_lower
    assert "and" not in keywords_lower
    assert "or" not in keywords_lower
    # Should have content words
    assert any("water" in k.lower() or "bottle" in k.lower() or "steel" in k.lower() for k in keywords)


def test_extract_keywords_returns_top_n():
    """Test that top N keywords are returned and sorted by frequency"""
    serp_data = {
        "organic_results": [
            {"title": "water bottle water bottle water bottle", "snippet": "bottle is great bottle is great"},
            {"title": "stainless steel bottle", "snippet": "steel insulated bottle"}
        ],
        "related_searches": ["water bottle", "water bottle"]
    }
    
    keywords = extract_keywords(serp_data, top_n=5)
    
    assert len(keywords) <= 5
    assert len(keywords) > 0
    # 'bottle' and 'water' should be high frequency
    keywords_lower = [k.lower() for k in keywords]
    assert any("bottle" in k for k in keywords_lower)


def test_extract_keywords_handles_empty_data():
    """Test that empty data returns empty list without crashing"""
    serp_data = {
        "organic_results": [],
        "related_searches": []
    }
    
    keywords = extract_keywords(serp_data)
    
    assert keywords == []


def test_extract_keywords_handles_missing_keys():
    """Test that missing 'organic_results' or 'related_searches' keys don't crash"""
    serp_data = {}  # No keys at all
    
    keywords = extract_keywords(serp_data)
    
    assert keywords == []


def test_extract_keywords_with_partial_data():
    """Test extraction with only organic_results, no related_searches"""
    serp_data = {
        "organic_results": [
            {"title": "premium water bottle", "snippet": "insulated water bottle"}
        ]
        # No related_searches key
    }
    
    keywords = extract_keywords(serp_data, top_n=5)
    
    assert len(keywords) > 0
    keywords_lower = [k.lower() for k in keywords]
    assert any("water" in k or "bottle" in k for k in keywords_lower)
