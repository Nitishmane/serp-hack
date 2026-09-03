const form = document.getElementById('generatorForm');
const submitBtn = document.getElementById('submitBtn');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const productName = document.getElementById('productName').value.trim();
    if (!productName) return;

    setLoading(true);
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
            showError(data.detail || 'Something went wrong. Please try again.');
            return;
        }

        displayResults(data);
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        setLoading(false);
    }
});

function displayResults(data) {
    setField('resultTitle', data.title);
    setField('resultDescription', data.description);

    setCounter('titleCounter', data.title, 200);
    setCounter('descCounter', data.description, 300);

    document.getElementById('resultBullets').innerHTML =
        (data.bullets || []).map(b => `<li>${esc(b)}</li>`).join('');

    document.getElementById('resultKeywords').innerHTML =
        (data.keywords_used || []).map(k => `<span class="tag">${esc(k)}</span>`).join('');

    renderPositioning(data);
    renderCompetitors(data.sources || {});
    renderSources(data.sources || {});

    show('results');
    document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderPositioning(data) {
    const card = document.getElementById('positioningCard');
    const price = data.suggested_price || '';
    const positioning = data.positioning || '';
    if (!price && !positioning) { card.classList.add('hidden'); return; }
    card.classList.remove('hidden');
    document.getElementById('resultPrice').textContent = price;
    document.getElementById('resultPositioning').textContent = positioning || '—';
}

function renderCompetitors(sources) {
    const card = document.getElementById('competitorCard');
    const comps = sources.amazon_competitors || [];
    const stats = sources.price_stats;

    if (!comps.length) { card.classList.add('hidden'); return; }
    card.classList.remove('hidden');

    document.getElementById('priceRange').textContent =
        stats ? `$${stats.min} – $${stats.max} · median $${stats.median}` : `${comps.length} listings`;

    document.getElementById('resultCompetitors').innerHTML = comps.map(c => `
        <div class="comp-row">
            <span class="comp-name">${esc(c.title)}</span>
            <span class="comp-stats">
                ${c.price ? `<span class="comp-price">${esc(c.price)}</span>` : ''}
                ${c.rating ? `<span class="comp-rating">${esc(c.rating)}★</span>` : ''}
                ${c.reviews ? `<span class="comp-reviews">${esc(String(c.reviews))} rev</span>` : ''}
            </span>
        </div>
    `).join('');
}

function renderSources(sources) {
    const signals = sources.signal_count ?? 0;
    const engines = sources.engines_used || [];
    const autocomplete = sources.autocomplete || [];

    document.getElementById('signalCount').textContent = `${signals} signals`;

    let html = '';
    if (engines.length) {
        html += '<div class="src-label">Engines used</div><div class="tags">';
        html += engines.map(e => `<span class="tag engine">${esc(e)}</span>`).join('');
        html += '</div>';
    }
    if (autocomplete.length) {
        html += '<div class="src-label" style="margin-top:.9rem">What shoppers search for</div><div class="tags">';
        html += autocomplete.map(a => `<span class="tag">${esc(a)}</span>`).join('');
        html += '</div>';
    }
    if (!html) html = '<div class="comp-item">No additional research signals for this query.</div>';
    document.getElementById('resultSources').innerHTML = html;
}

function setField(id, value) {
    document.getElementById(id).textContent = value || '';
}

function setCounter(id, value, max) {
    const len = (value || '').length;
    document.getElementById(id).textContent = `${len} / ${max} characters`;
}

function setLoading(on) {
    submitBtn.disabled = on;
    submitBtn.textContent = on ? 'Generating…' : 'Generate';
    on ? show('loading') : hide('loading');
}

function showError(msg) {
    document.querySelector('#error .error-message').textContent = msg;
    show('error');
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

function esc(str) {
    return String(str).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

// Copy-to-clipboard (buttons reference their target field via data-copy)
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.copy);
        if (!target) return;
        navigator.clipboard.writeText(target.textContent).then(() => {
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = 'Copy';
                btn.classList.remove('copied');
            }, 1800);
        });
    });
});
