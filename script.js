/* ── Scroll-triggered animations ── */
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));

/* ── Search helpers ── */
function fillSearch(text) {
    const q = document.getElementById('query');
    if (!q) return;
    q.value = text;
    q.focus();
}

async function searchProducts() {
    const query    = document.getElementById('query')?.value?.trim();
    const results  = document.getElementById('results');
    const budget   = document.getElementById('budget')?.value   || '';
    const category = document.getElementById('category')?.value || '';
    const purpose  = document.getElementById('purpose')?.value  || '';

    if (!query) return;

    results.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;padding:24px 0;color:rgba(255,255,255,0.5);">
            <div style="width:20px;height:20px;border:2px solid #ff6b00;border-top-color:transparent;border-radius:50%;animation:spin 0.7s linear infinite;"></div>
            Searching for <strong style="color:white;">${query}</strong>…
        </div>`;

    const params = new URLSearchParams({ q: query });
    if (budget)   params.append('budget',   budget);
    if (category) params.append('category', category);
    if (purpose)  params.append('purpose',  purpose);

    try {
        const response = await fetch(`/search?${params}`);
        const data     = await response.json();

        if (!data.products || data.products.length === 0) {
            results.innerHTML = `
                <div style="text-align:center;padding:48px 0;color:rgba(255,255,255,0.4);">
                    <div style="font-size:48px;margin-bottom:16px;">🔍</div>
                    <p style="font-size:16px;">No results found for "<strong style="color:white;">${query}</strong>"</p>
                    <p style="margin-top:8px;font-size:14px;">Try a different keyword or adjust your filters.</p>
                </div>`;
            return;
        }

        const sourceBadge = data.source === 'live'
            ? `<span style="background:linear-gradient(135deg,#00c853,#00897b);color:white;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;margin-left:10px;vertical-align:middle;">🔴 LIVE</span>`
            : `<span style="background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.5);font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px;margin-left:10px;vertical-align:middle;">LOCAL</span>`;

        results.innerHTML = `<p style="color:rgba(255,255,255,0.45);margin-bottom:20px;font-size:14px;">${data.total} result${data.total !== 1 ? 's' : ''} found ${sourceBadge}</p>`;

        data.products.forEach((product, i) => {
            const card = document.createElement('div');
            card.className = 'result-card';
            card.style.animationDelay = `${i * 0.08}s`;

            const thumb = product.thumbnail
                ? `<img src="${product.thumbnail}" alt="${product.name}"
                       style="width:90px;height:90px;object-fit:contain;border-radius:10px;background:rgba(255,255,255,0.06);padding:6px;flex-shrink:0;">`
                : '';

            const buyBtn = product.url
                ? `<a href="${product.url}" target="_blank" rel="noopener"
                      style="display:inline-block;padding:10px 22px;background:linear-gradient(135deg,#ff6b00,#ff3aff);border-radius:50px;color:white;font-weight:700;font-size:13px;text-decoration:none;">
                      ${product.live ? '🛒 Buy Now' : '🔗 View Deal'} →
                   </a>`
                : '';

            const amazonBtn = product.amazon_url
                ? `<a href="${product.amazon_url}" target="_blank" rel="noopener"
                      style="display:inline-block;padding:10px 22px;background:linear-gradient(135deg,#ff9900,#e47911);border-radius:50px;color:white;font-weight:700;font-size:13px;text-decoration:none;">
                      🛒 Find on Amazon
                   </a>`
                : '';

            const sourceTag = product.source
                ? `<span style="font-size:12px;color:rgba(255,255,255,0.4);margin-left:8px;">via ${product.source}</span>` : '';

            card.innerHTML = `
                <div style="display:flex;gap:16px;align-items:flex-start;">
                    ${thumb}
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;">
                            <div style="flex:1;">
                                <h3 style="font-size:17px;margin-bottom:4px;line-height:1.3;">${product.name}</h3>
                                <p style="color:rgba(255,255,255,0.45);font-size:12px;margin-bottom:10px;">${product.category}${sourceTag}</p>
                                <p style="color:rgba(255,255,255,0.7);font-size:14px;line-height:1.6;">${product.description || ''}</p>
                            </div>
                            <div style="text-align:right;flex-shrink:0;">
                                <div style="font-size:24px;font-weight:800;color:#ff6b00;">${product.price}</div>
                                <div style="font-size:12px;margin-top:3px;color:rgba(255,255,255,0.6);">${product.rating}</div>
                            </div>
                        </div>
                        <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap;">
                            ${buyBtn}
                            ${product.live ? amazonBtn : ''}
                        </div>
                    </div>
                </div>
            `;
            results.appendChild(card);
        });
    } catch (err) {
        results.innerHTML = `<p style="color:rgba(255,255,255,0.4);padding:20px 0;">Could not reach the server. Make sure the backend is running.</p>`;
    }
}

/* ── Contact form ── */
function handleSubmit(e) {
    e.preventDefault();
    const msg = document.getElementById('form-msg');
    if (msg) {
        msg.style.display = 'block';
        e.target.reset();
    }
}
