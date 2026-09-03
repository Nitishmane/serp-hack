# Amazon FBA Listing Generator

> Turn any product name into a keyword-optimized Amazon title, description, bullets, a competitive price, and a positioning angle, powered by live multi-engine competitor research and GLM 5.3 Flash.

## Inspiration

Anyone selling on Amazon FBA knows the quiet tax of the platform: the listing is the product. A brilliant water bottle with a lazy title sinks below page one, while a mediocre one with keyword-rich copy floats to the top. Writing that copy means hours of squinting at competitor listings, guessing at which keywords the A9 search algorithm rewards, and rewriting the same "Premium, Eco-Friendly, Durable" incantations over and over.

We wanted to compress that whole loop (research, then keywords, then a polished listing) into a single text box and one click. Type "stainless steel water bottle" and get back a ready-to-paste title, description, bullet points, a competitive price, and a positioning angle that were all informed by what is actually ranking right now.

## How we built it

The pipeline is small and legible. Live research fans out across three SerpApi engines in parallel, then feeds a single language model call:

$$
\text{product} \xrightarrow{\text{SerpApi}} \text{signals} \xrightarrow{\text{extract}} \text{keywords} \xrightarrow{\text{GLM 5.3}} \text{listing}
$$

- Research runs three engines concurrently: Google Search (organic titles, related searches, people-also-ask), Amazon (real competitor listings with prices, ratings, and review counts), and Google Autocomplete (long-tail phrases buyers actually type).
- Keyword extraction is pure Python, no heavy NLP: tokenize, drop stopwords, generate unigrams and bigrams, and rank by frequency. Given a corpus of tokens $T$, we score each n-gram $g$ by its raw count and keep the top $k$:

$$
\text{score}(g) = \sum_{t \in T} \mathbb{1}[t = g], \qquad K = \operatorname*{arg\,top\text{-}}k_{\,g}\ \text{score}(g)
$$

- We also compute price statistics from the Amazon results (min, median, max) so the model can price competitively instead of guessing.
- GLM 5.3 Flash, called via OpenRouter with the OpenAI-compatible SDK, turns the product plus this research brief into structured output. We force tool calling so the model must return a valid object of title, description, bullets, suggested price, and positioning. No fragile parsing of prose or markdown fences.
- FastAPI ties it together behind a single POST /generate endpoint, with a dependency-free HTML, CSS, and JS frontend. The whole thing is deployed as a Python serverless function on Vercel.

## What we learned

- Reasoning models do not behave like chat models. GLM 5.3 Flash always reasons, and those reasoning tokens are billed against max_tokens. Our tool arguments were silently being starved of budget.
- Structured output does not mean safe output. Forcing a tool call guarantees a shape, not a complete payload. A response truncated mid-generation still arrives as a tool call, just an empty one.
- A max is not a target. Telling a model to use at most 300 characters makes it treat 300 as a ceiling to stay far away from, not a space to fill.
- Parallelism is nearly free here. Running three SerpApi engines concurrently costs about the wall-clock time of one, so richer research did not cost us latency.
- Provider swaps are mostly about the seams. Anthropic hands you a parsed dict; OpenAI and OpenRouter hand you a JSON string that you must parse yourself, a small difference that is the whole ballgame in error handling.

## Challenges we faced

1. The vanishing title. In production, /generate kept returning a 500 with "Model tool response missing title" after about 30 seconds. The culprit was the token budget. With max_tokens = 1000, reasoning alone consumed roughly 700 to 850 tokens:

$$
\underbrace{r}_{\approx 700\text{-}850} + \underbrace{a}_{\text{tool args} \approx 250} \;>\; 1000 = M_{\max}
$$

Once $r + a > M_{\max}$, the arguments truncated to an empty object: valid JSON, no title. The fix was two-fold: set reasoning effort to low (dropping latency from about 30 seconds to 4 to 17 seconds) and raise max_tokens to 3000 for headroom.

2. A locked reasoning switch. The obvious move, turning reasoning off, returned a 400: "Reasoning is mandatory for this endpoint and cannot be disabled." So we could not eliminate the reasoning tax, only budget around it and dial its effort down.

3. Deploying under SAML. The first Vercel token was scoped to a SAML-enforced team, so every deploy call bounced with a re-authentication demand. Swapping in a personal-scoped token, plus creating the project and pushing environment variables through the Vercel REST API, got us shipped.

4. Copy that overshot. Once we asked for richer, research-driven descriptions, the model started blowing past the 300-character cap and hard-failing the request. We switched from rejecting overflow to trimming at a sentence or word boundary, so a slightly long answer degrades gracefully instead of erroring.

## What's next

Cross-retailer price benchmarking with a Google Shopping engine, an A/B mode that generates several title variants and scores them, real per-category Amazon character-limit validation, and persistence so sellers can save and compare listings.
