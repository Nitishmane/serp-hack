document.getElementById('generatorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const productName = document.getElementById('productName').value.trim();
    if (!productName) return;
    
    show('loading');
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
            showError(data.detail || 'Unknown error');
            return;
        }
        
        displayResults(data);
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        hide('loading');
    }
});

function displayResults(data) {
    document.getElementById('resultTitle').textContent = data.title;
    document.getElementById('resultDescription').textContent = data.description;
    document.getElementById('resultBullets').innerHTML = 
        data.bullets.map(b => `<li>${b}</li>`).join('');
    document.getElementById('resultKeywords').innerHTML = 
        data.keywords_used.map(k => `<span class="tag">${k}</span>`).join('');
    
    const sourcesInfo = data.sources;
    const sourcesHTML = `
        <p><strong>Competitors found:</strong> ${sourcesInfo.competitor_titles_found.length}</p>
        <p><strong>Total signals:</strong> ${sourcesInfo.signal_count}</p>
    `;
    document.getElementById('resultSources').innerHTML = sourcesHTML;
    
    show('results');
}

function showError(msg) {
    document.querySelector('#error .error-message').textContent = msg;
    show('error');
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

// Copy-to-clipboard
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const field = btn.previousElementSibling;
        navigator.clipboard.writeText(field.textContent);
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
});
