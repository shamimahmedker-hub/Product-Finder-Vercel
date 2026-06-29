import os
import re
import requests as req
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SERPAPI_KEY       = os.environ.get('SERPAPI_KEY', '')
AMAZON_AFFILIATE  = os.environ.get('AMAZON_AFFILIATE_TAG', '')

# ── Amazon affiliate link helper ───────────────────────────────────────────────
def affiliate_url(url: str) -> str:
    """Append Amazon affiliate tag to any Amazon product URL."""
    if not AMAZON_AFFILIATE:
        return url
    if 'amazon.com' in url:
        sep = '&' if '?' in url else '?'
        return f"{url}{sep}tag={AMAZON_AFFILIATE}"
    # For non-Amazon links, wrap with Amazon search for the same product
    return url


def amazon_search_url(query: str) -> str:
    """Build an Amazon search URL with affiliate tag."""
    encoded = req.utils.quote(query, safe='')
    base = f"https://www.amazon.com/s?k={encoded}"
    if AMAZON_AFFILIATE:
        base += f"&tag={AMAZON_AFFILIATE}"
    return base


# ── Query cleaner ─────────────────────────────────────────────────────────
def clean_query(query: str) -> tuple[str, int | None]:
    """
    Strip filler words and extract budget from natural language query.
    e.g. "top 10 monitors to buy in $3000" → ("monitors", 3000)
    """
    # Extract budget from query
    budget_match = re.search(r'\$\s*(\d[\d,]*)', query)
    budget_val   = None
    if budget_match:
        budget_val = int(budget_match.group(1).replace(',', ''))

    # Remove filler phrases — word-boundary safe
    cleaned = query
    fillers = [
        r'top\s+\d+\s*',          # "top 10"
        r'best\s+\d+\s*',         # "best 5"
        r'\d+\s+best\s*',         # "5 best"
        r'\bto\s+buy\b',          # "to buy"
        r'\bto\s+purchase\b',     # "to purchase"
        r'\bunder\s+\$[\d,]+',    # "under $3000"
        r'\bbelow\s+\$[\d,]+',    # "below $3000"
        r'\bin\s+\$[\d,]+',       # "in $3000"
        r'\bfor\s+\$[\d,]+',      # "for $3000"
        r'\baround\s+\$[\d,]+',   # "around $3000"
        r'\bupto\s+\$[\d,]+',     # "upto $3000"
        r'\bup\s+to\s+\$[\d,]+',  # "up to $3000"
        r'\$[\d,]+',              # bare "$3000"
        r'\bbest\b',              # lone "best"
        r'\btop\b',               # lone "top"
        r'\bbuy\b',               # lone "buy"
    ]
    for pattern in fillers:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.')
    return cleaned or query, budget_val


# ── SerpAPI live search ───────────────────────────────────────────────────────
def serpapi_search(query: str, budget: str = None) -> list:
    """Fetch real Google Shopping results from SerpAPI."""
    clean_q, extracted_budget = clean_query(query)

    # Prefer explicit filter budget, then query-extracted budget
    effective_budget = None
    if budget:
        effective_budget = int(budget)
    elif extracted_budget:
        effective_budget = extracted_budget

    # Append budget naturally so Google Shopping understands it
    search_q = f"{clean_q} under ${effective_budget}" if effective_budget else clean_q

    params = {
        'engine':  'google_shopping',
        'q':       search_q,
        'api_key': SERPAPI_KEY,
        'num':     '20',
        'gl':      'us',
        'hl':      'en',
    }

    try:
        resp = req.get('https://serpapi.com/search.json', params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f'SerpAPI error: {e}')
        return []

    products = []
    for item in data.get('shopping_results', []):
        if len(products) >= 10:
            break

        raw_price  = item.get('price', 'See price')
        price_num  = 0
        price_clean = re.sub(r'[^\d.]', '', str(raw_price).split('-')[0])
        if price_clean:
            try:
                price_num = float(price_clean)
            except ValueError:
                pass

        # Secondary hard filter — drop anything clearly over budget
        if effective_budget and price_num and price_num > effective_budget * 1.05:
            continue

        rating_val = item.get('rating', '')
        rating_str = f'⭐ {rating_val}' if rating_val else '⭐ —'
        reviews    = item.get('reviews')
        if reviews:
            rating_str += f' ({reviews:,} reviews)'

        source = item.get('source', '')
        link   = item.get('link') or amazon_search_url(item.get('title', query))
        if 'amazon' in link.lower() or 'amazon' in source.lower():
            link = affiliate_url(link)

        products.append({
            'name':        item.get('title', 'Unknown Product'),
            'price':       raw_price,
            'rating':      rating_str,
            'category':    source or 'Online',
            'description': item.get('snippet', ''),
            'url':         link,
            'amazon_url':  amazon_search_url(item.get('title', query)),
            'thumbnail':   item.get('thumbnail', ''),
            'source':      source,
            'live':        True,
        })

    return products


# ── Fallback local product database ───────────────────────────────────────────
PRODUCTS = [
    {"id": 1,  "name": "Apple MacBook Air M2",        "price": "$1,099", "rating": "⭐ 4.9", "category": "Laptops",    "purpose": ["Office Work","Professional","Students"], "budget": 2000, "description": "Powerful ultrabook with M2 chip", "url": "https://www.amazon.com/s?k=MacBook+Air+M2"},
    {"id": 2,  "name": "Dell XPS 15",                 "price": "$999",   "rating": "⭐ 4.7", "category": "Laptops",    "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "Premium Windows laptop", "url": "https://www.amazon.com/s?k=Dell+XPS+15"},
    {"id": 3,  "name": "Lenovo ThinkPad X1 Carbon",   "price": "$899",   "rating": "⭐ 4.8", "category": "Laptops",    "purpose": ["Office Work","Travel"],                  "budget": 1000, "description": "Business laptop", "url": "https://www.amazon.com/s?k=Lenovo+ThinkPad+X1"},
    {"id": 4,  "name": "Acer Aspire 5",               "price": "$399",   "rating": "⭐ 4.4", "category": "Laptops",    "purpose": ["Students","Office Work"],                "budget": 500,  "description": "Budget friendly laptop", "url": "https://www.amazon.com/s?k=Acer+Aspire+5"},
    {"id": 5,  "name": "ASUS ROG Strix G16",          "price": "$1,299", "rating": "⭐ 4.8", "category": "Laptops",    "purpose": ["Gaming"],                               "budget": 2000, "description": "Gaming powerhouse", "url": "https://www.amazon.com/s?k=ASUS+ROG+Strix"},
    {"id": 6,  "name": "HP Pavilion 15",              "price": "$549",   "rating": "⭐ 4.3", "category": "Laptops",    "purpose": ["Students","Office Work","Travel"],       "budget": 1000, "description": "Versatile laptop", "url": "https://www.amazon.com/s?k=HP+Pavilion+15"},
    {"id": 7,  "name": "Microsoft Surface Laptop 5",  "price": "$999",   "rating": "⭐ 4.6", "category": "Laptops",    "purpose": ["Office Work","Professional"],            "budget": 1000, "description": "Sleek Windows laptop", "url": "https://www.amazon.com/s?k=Microsoft+Surface"},
    {"id": 8,  "name": "Sony WH-1000XM5",             "price": "$299",   "rating": "⭐ 4.9", "category": "Headphones", "purpose": ["Office Work","Travel","Professional"],   "budget": 300,  "description": "Best noise canceling", "url": "https://www.amazon.com/s?k=Sony+WH-1000XM5"},
    {"id": 9,  "name": "Apple AirPods Pro 2",         "price": "$249",   "rating": "⭐ 4.8", "category": "Headphones", "purpose": ["Travel","Office Work"],                  "budget": 300,  "description": "Premium wireless", "url": "https://www.amazon.com/s?k=AirPods+Pro"},
    {"id": 10, "name": "SteelSeries Arctis Nova Pro", "price": "$149",   "rating": "⭐ 4.7", "category": "Headphones", "purpose": ["Gaming"],                               "budget": 300,  "description": "Gaming headset", "url": "https://www.amazon.com/s?k=SteelSeries+Arctis"},
    {"id": 11, "name": "Anker Soundcore Q45",         "price": "$59",    "rating": "⭐ 4.5", "category": "Headphones", "purpose": ["Students","Travel"],                     "budget": 100,  "description": "Budget headphones", "url": "https://www.amazon.com/s?k=Anker+Soundcore"},
    {"id": 12, "name": "Bose QuietComfort 45",        "price": "$229",   "rating": "⭐ 4.7", "category": "Headphones", "purpose": ["Travel","Office Work"],                  "budget": 300,  "description": "Premium comfort", "url": "https://www.amazon.com/s?k=Bose+QuietComfort"},
    {"id": 13, "name": "iPhone 15 Pro",               "price": "$999",   "rating": "⭐ 4.9", "category": "Phones",     "purpose": ["Professional","Travel"],                 "budget": 1000, "description": "Latest Apple phone", "url": "https://www.amazon.com/s?k=iPhone+15+Pro"},
    {"id": 14, "name": "Samsung Galaxy S24",          "price": "$799",   "rating": "⭐ 4.8", "category": "Phones",     "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "Premium Android", "url": "https://www.amazon.com/s?k=Samsung+Galaxy+S24"},
    {"id": 15, "name": "Google Pixel 8a",             "price": "$499",   "rating": "⭐ 4.7", "category": "Phones",     "purpose": ["Students","Office Work","Travel"],       "budget": 500,  "description": "Mid-range Android", "url": "https://www.amazon.com/s?k=Google+Pixel+8a"},
    {"id": 16, "name": "Sony ZV-E10",                 "price": "$598",   "rating": "⭐ 4.7", "category": "Cameras",    "purpose": ["Professional","Travel"],                 "budget": 1000, "description": "Mirrorless camera", "url": "https://www.amazon.com/s?k=Sony+ZV-E10"},
    {"id": 17, "name": "Canon EOS Rebel SL3",         "price": "$649",   "rating": "⭐ 4.6", "category": "Cameras",    "purpose": ["Students","Travel"],                     "budget": 1000, "description": "Entry DSLR", "url": "https://www.amazon.com/s?k=Canon+EOS+Rebel"},
    {"id": 18, "name": "GoPro HERO12 Black",          "price": "$349",   "rating": "⭐ 4.7", "category": "Cameras",    "purpose": ["Travel","Gaming"],                       "budget": 500,  "description": "Action camera", "url": "https://www.amazon.com/s?k=GoPro+HERO12"},
    {"id": 19, "name": "LG 27GP850-B",                "price": "$299",   "rating": "⭐ 4.8", "category": "Monitors",   "purpose": ["Gaming","Professional"],                 "budget": 300,  "description": "Gaming monitor", "url": "https://www.amazon.com/s?k=LG+27GP850"},
    {"id": 20, "name": "Dell UltraSharp U2723DE",     "price": "$649",   "rating": "⭐ 4.9", "category": "Monitors",   "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "Professional monitor", "url": "https://www.amazon.com/s?k=Dell+UltraSharp"},
    {"id": 21, "name": "Samsung Odyssey G7",          "price": "$449",   "rating": "⭐ 4.7", "category": "Monitors",   "purpose": ["Gaming"],                               "budget": 500,  "description": "Gaming monitor", "url": "https://www.amazon.com/s?k=Samsung+Odyssey"},
]


def local_search(query: str, budget=None, category=None, purpose=None) -> list:
    query_lower = query.lower()
    results = []
    cat_map = {
        "laptop": "Laptops", "laptops": "Laptops", "notebook": "Laptops",
        "headphone": "Headphones", "headphones": "Headphones",
        "earphone": "Headphones", "earbud": "Headphones",
        "phone": "Phones", "smartphone": "Phones", "mobile": "Phones",
        "camera": "Cameras", "dslr": "Cameras", "mirrorless": "Cameras",
        "monitor": "Monitors", "display": "Monitors", "screen": "Monitors",
    }
    purp_map = {
        "gaming": "Gaming", "game": "Gaming",
        "office": "Office Work", "work": "Office Work", "business": "Office Work",
        "travel": "Travel", "portable": "Travel",
        "student": "Students", "college": "Students", "school": "Students",
        "professional": "Professional", "pro": "Professional", "creator": "Professional",
    }

    for p in PRODUCTS:
        score = 0
        if any(w in p["name"].lower()        for w in query_lower.split()): score += 3
        if any(w in p["description"].lower() for w in query_lower.split()): score += 1
        for kw, cat in cat_map.items():
            if kw in query_lower and p["category"] == cat: score += 4
        for kw, purp in purp_map.items():
            if kw in query_lower and purp in p["purpose"]: score += 3

        bm = re.search(r'\$?(\d{2,4})', query)
        if bm:
            pb = int(bm.group(1))
            score += 2 if p["budget"] <= pb else -3

        if budget   and p["budget"] > int(budget):      score -= 5
        if category and p["category"].lower() != category.lower(): score -= 5
        if purpose  and purpose not in p["purpose"]:    score -= 3

        if score > 0:
            results.append((score, p))

    results.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, p in results[:6]:
        prod = dict(p)
        prod['url']        = affiliate_url(prod['url'])
        prod['amazon_url'] = amazon_search_url(prod['name'])
        prod['live']       = False
        out.append(prod)
    return out


# ── Routes ───────────────────────────────────────────────────────────
# Google Search Console verification file - MUST be before catch-all
@app.route('/google<path:filename>')
def google_verification(filename):
    """Serve Google Search Console verification files directly."""
    full_filename = f"google{filename}"
    try:
        return send_from_directory('.', full_filename)
    except Exception as e:
        print(f"Error serving {full_filename}: {e}")
        return "File not found", 404


@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/search')
def search():
    query    = request.args.get('q', '').strip()
    budget   = request.args.get('budget')   or None
    category = request.args.get('category') or None
    purpose  = request.args.get('purpose')  or None

    if not query:
        return jsonify({"products": [], "message": "Please enter a search query."})

    # Use SerpAPI if key is configured, else fall back to local DB
    if SERPAPI_KEY:
        products = serpapi_search(query, budget=budget)
        source   = 'live'
    else:
        products = []
        source   = 'local'

    if not products:
        products = local_search(query, budget=budget, category=category, purpose=purpose)
        source   = 'local'

    if not products:
        return jsonify({"products": [], "total": 0, "source": source,
                        "message": f"No products found for '{query}'."})

    return jsonify({"products": products, "total": len(products), "source": source})


@app.route('/status')
def status():
    return jsonify({
        "serpapi":  bool(SERPAPI_KEY),
        "affiliate": bool(AMAZON_AFFILIATE),
        "affiliate_tag": AMAZON_AFFILIATE or None,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
