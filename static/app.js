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

    renderSources(data.sources || {});

    show('results');
    document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderSources(sources) {
    const competitors = sources.competitor_titles_found || [];
    const signals = sources.signal_count ?? 0;

    document.getElementById('signalCount').textContent = `${signals} signals`;

    let html = '';
    if (competitors.length) {
        html += '<div class="src-label">Competitor titles analyzed</div><div class="comp-list">';
        html += competitors
            .map((t, i) => `<div class="comp-item"><span class="idx">${i + 1}.</span><span>${esc(t)}</span></div>`)
            .join('');
        html += '</div>';
    } else {
        html = '<div class="comp-item">No competitor titles were returned for this query.</div>';
    }
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
