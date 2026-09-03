# Amazon FBA Listing Generator

> **Turn any product name into a keyword-optimized Amazon title, description, and bullets — powered by live competitor research and GLM 5.3 Flash.**

## 💡 Inspiration

Anyone selling on Amazon FBA knows the quiet tax of the platform: **the listing is the product**. A brilliant water bottle with a lazy title sinks below page one, while a mediocre one with keyword-rich copy floats to the top. Writing that copy means hours of squinting at competitor listings, guessing at which keywords the A9 search algorithm rewards, and rewriting the same "Premium • Eco-Friendly • Durable" incantations over and over.

We wanted to compress that whole loop — **research → keywords → polished listing** — into a single text box and one click. Type "stainless steel water bottle," get back a ready-to-paste title, description, and bullet points that were actually informed by what's ranking *right now*.

## 🛠️ How we built it

The pipeline is deliberately small and legible — four stages, each doing one thing:

$$
\text{product} \xrightarrow{\text{SerpAPI}} \text{SERP} \xrightarrow{\text{extract}} \text{keywords} \xrightarrow{\text{GLM 5.3}} \text{listing}
$$

- **SerpAPI** pulls the live Google results for the product — organic titles, snippets, and related searches — as our competitive signal.
- **Keyword extraction** is pure Python, no heavy NLP: tokenize, drop stopwords, generate unigrams + bigrams, and rank by frequency. Given a corpus of tokens $T$, we score each n-gram $g$ by its raw count and keep the top $k$:

$$
\text{score}(g) = \sum_{t \in T} \mathbb{1}[t = g], \qquad K = \operatorname*{arg\,top-}k_{\,g}\ \text{score}(g)
$$

- **GLM 5.3 Flash** (via **OpenRouter**, using the OpenAI-compatible SDK) turns the product + keywords into structured output. We force **tool calling** so the model must return a valid `{title, description, bullets}` object — no fragile parsing of prose or markdown fences.
- **FastAPI** ties it together behind a `POST /generate` endpoint, with a dependency-free vanilla HTML/CSS/JS frontend. The whole thing is deployed as a **Python serverless function on Vercel**.

## 📚 What we learned

- **Reasoning models don't behave like chat models.** GLM 5.3 Flash *always* reasons, and — crucially — those reasoning tokens are billed against `max_tokens`. Our tool arguments were silently being starved of budget.
- **"Structured output" doesn't mean "safe output."** Forcing a tool call guarantees a *shape*, not a *complete* payload. A response truncated mid-generation still arrives as a tool call — just an empty one.
- **A `max` is not a target.** Telling an LLM "≤ 300 characters" makes it treat 300 as a ceiling to stay far away from, not a space to fill.
- **Provider swaps are mostly about the seams.** Anthropic hands you a parsed dict; OpenAI/OpenRouter hands you a JSON *string* that you must `json.loads` yourself — a small difference that's the whole ballgame in error handling.

## 🧗 Challenges we faced

**1. The vanishing `title`.** In production, `/generate` kept returning `500: Model tool response missing 'title'` after ~30s. The culprit was the token budget. With `max_tokens = 1000`, reasoning alone consumed ~700–850 tokens:

$$
\underbrace{r}_{\approx 700\text{–}850} + \underbrace{a}_{\text{tool args} \approx 250} \;>\; 1000 = M_{\max}
$$

Once $r + a > M_{\max}$, the arguments truncated to `{}` — valid JSON, no `title`. The fix was two-fold: set `reasoning: {effort: "low"}` (dropping latency from ~30s to ~4–17s) and raise `max_tokens` to 3000 for headroom.

**2. A locked reasoning switch.** The obvious move — turn reasoning *off* — returned `400: Reasoning is mandatory for this endpoint and cannot be disabled`. So we couldn't eliminate the reasoning tax, only budget around it and dial its effort down.

**3. Deploying under SAML.** The first Vercel token was scoped to a SAML-enforced team, so every deploy call bounced with a re-authentication demand. Swapping in a personal-scoped token — plus creating the project and pushing env vars through the Vercel REST API — got us shipped.

**4. Thin descriptions.** Even once it worked, the copy felt undersized (~130–190 chars). Rewriting the prompt to give **target ranges** ("240–300 characters, a full flowing paragraph — don't stop short") instead of a bare cap brought descriptions up to a healthy ~200–270.

## 🚀 What's next

Multi-query SerpAPI research (people-also-ask, autocomplete), an A/B mode that generates several title variants and scores them, real Amazon character-limit validation per category, and persistence so sellers can save and compare listings.
