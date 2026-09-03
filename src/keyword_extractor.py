import re
from collections import Counter
from typing import List


# Simple English stopwords
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'for', 'in', 'on', 'is', 'be', 'are', 'was', 'were',
    'to', 'of', 'with', 'by', 'from', 'as', 'at', 'it', 'that', 'this', 'which', 'who',
    'if', 'but', 'not', 'no', 'so', 'up', 'can', 'will', 'do', 'does', 'did', 'has',
    'have', 'he', 'she', 'you', 'we', 'me', 'him', 'her', 'them', 'my', 'your', 'its',
    'all', 'each', 'every', 'both', 'other', 'than', 'then', 'what', 'where', 'when',
    'why', 'how', 'about', 'through', 'during', 'before', 'after', 'above', 'below',
    'into', 'out', 'off', 'over', 'under', 'again', 'further', 'only', 'own', 'same',
    'so', 'such', 'should', 'now', 'am', 'been', 'being', 'having', 'may', 'might',
    'must', 'should', 'could', 'would', 'should'
}


def tokenize_and_filter(text_list: List[str]) -> List[str]:
    """
    Tokenize text by whitespace and punctuation, convert to lowercase,
    and filter out stopwords.
    
    Args:
        text_list: List of text strings
    
    Returns:
        List of lowercase tokens (stopwords removed)
    """
    tokens = []
    
    for text in text_list:
        if not text:
            continue
        
        # Convert to lowercase
        text = text.lower()
        
        # Split by whitespace and punctuation using regex
        # Keep only alphanumeric and common characters like hyphens
        words = re.findall(r'\b[a-z0-9]+(?:-[a-z0-9]+)?\b', text)
        
        # Filter out stopwords
        for word in words:
            if word and word not in STOPWORDS:
                tokens.append(word)
    
    return tokens


def extract_ngrams(tokens: List[str], n: List[int] = None) -> List[str]:
    """
    Extract n-grams from tokenized text.
    
    Args:
        tokens: List of tokens
        n: List of n-gram sizes (default: [1, 2] for unigrams and bigrams)
    
    Returns:
        List of n-grams as strings
    """
    if n is None:
        n = [1, 2]
    
    ngrams = []
    
    for gram_size in n:
        for i in range(len(tokens) - gram_size + 1):
            gram = " ".join(tokens[i:i + gram_size])
            ngrams.append(gram)
    
    return ngrams


def sort_by_frequency(ngrams: List[str], top_n: int = 15) -> List[str]:
    """
    Count n-gram frequencies and return top N sorted by frequency (descending).
    
    Args:
        ngrams: List of n-grams
        top_n: Number of top n-grams to return
    
    Returns:
        List of top n-grams sorted by frequency
    """
    if not ngrams:
        return []
    
    counter = Counter(ngrams)
    # Sort by frequency (descending), then alphabetically for ties
    sorted_ngrams = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    
    return [ngram for ngram, count in sorted_ngrams[:top_n]]


def extract_keywords(serp_data: dict, top_n: int = 15) -> list:
    """
    Extract keywords from SerpApi response.
    Gracefully handles missing/empty keys: returns [] if no data.
    
    Args:
        serp_data: Dictionary from SerpAPI response
        top_n: Number of top keywords to return
    
    Returns:
        List of top keywords/phrases
    """
    all_text = []

    # Google organic titles + snippets
    for result in serp_data.get("organic_results") or []:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        if title:
            all_text.append(title)
        if snippet:
            all_text.append(snippet)

    # Google related searches + people-also-ask questions
    all_text.extend(s for s in (serp_data.get("related_searches") or []) if s)
    all_text.extend(q for q in (serp_data.get("related_questions") or []) if q)

    # Amazon competitor product titles (highest-signal for FBA)
    for product in serp_data.get("amazon_products") or []:
        if product.get("title"):
            all_text.append(product["title"])

    # Google Autocomplete long-tail phrases
    all_text.extend(s for s in (serp_data.get("autocomplete") or []) if s)

    if not all_text:
        return []  # No crash; just return empty list
    
    # Tokenize, filter stopwords, extract n-grams, rank by frequency
    tokens = tokenize_and_filter(all_text)
    if not tokens:
        return []
    
    ngrams = extract_ngrams(tokens, n=[1, 2])
    freq_sorted = sort_by_frequency(ngrams, top_n=top_n)
    
    return freq_sorted
