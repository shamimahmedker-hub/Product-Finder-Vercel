import os
import re
import requests as req
from urllib.parse import quote as url_quote
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SERPAPI_KEY       = os.environ.get('SERPAPI_KEY', '')
AMAZON_AFFILIATE  = os.environ.get('AMAZON_AFFILIATE_TAG', '')

def affiliate_url(url: str) -> str:
    if not AMAZON_AFFILIATE:
        return url
    if 'amazon.com' in url:
        sep = '&' if '?' in url else '?'
        return f"{url}{sep}tag={AMAZON_AFFILIATE}"
    return url

def amazon_search_url(query: str) -> str:
    encoded = url_quote(query, safe='')
    base = f"https://www.amazon.com/s?k={encoded}"
    if AMAZON_AFFILIATE:
        base += f"&tag={AMAZON_AFFILIATE}"
    return base

def clean_query(query: str):
    budget_match = re.search(r'\$\s*(\d[\d,]*)', query)
    budget_val   = None
    if budget_match:
        budget_val = int(budget_match.group(1).replace(',', ''))
    cleaned = query
    fillers = [
        r'top\s+\d+\s*', r'best\s+\d+\s*', r'\d+\s+best\s*',
        r'\bto\s+buy\b', r'\bto\s+purchase\b',
        r'\bunder\s+\$[\d,]+', r'\bbelow\s+\$[\d,]+', r'\bin\s+\$[\d,]+',
        r'\bfor\s+\$[\d,]+', r'\baround\s+\$[\d,]+', r'\bupto\s+\$[\d,]+',
        r'\bup\s+to\s+\$[\d,]+', r'\$[\d,]+',
        r'\bbest\b', r'\btop\b', r'\bbuy\b',
    ]
    for pattern in fillers:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.')
    return cleaned or query, budget_val

def serpapi_search(query: str, budget: str = None) -> list:
    clean_q, extracted_budget = clean_query(query)
    effective_budget = None
    if budget:
        try:
            effective_budget = int(budget)
        except (ValueError, TypeError):
            effective_budget = None
    elif extracted_budget:
        effective_budget = extracted_budget

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
        raw_price   = item.get('price', 'See price')
        price_num   = 0
        price_clean = re.sub(r'[^\d.]', '', str(raw_price).split('-')[0])
        if price_clean:
            try:
                price_num = float(price_clean)
            except ValueError:
                pass
        if effective_budget and price_num and price_num > effective_budget * 1.05:
            continue
        rating_val = item.get('rating', '')
        rating_str = f'⭐ {rating_val}' if rating_val else '⭐ —'
        reviews    = item.get('reviews')
        if reviews:
            rating_str += f' ({reviews:,} reviews)'
        source     = item.get('source', '')
        title      = item.get('title', query)
        amazon_url = amazon_search_url(title)
        products.append({
            'name':        item.get('title', 'Unknown Product'),
            'price':       raw_price,
            'rating':      rating_str,
            'category':    source or 'Online',
            'description': item.get('snippet', ''),
            'url':         amazon_url,
            'amazon_url':  amazon_url,
            'thumbnail':   item.get('thumbnail', ''),
            'source':      source,
            'live':        True,
        })
    return products

PRODUCTS = [
    {"id": 1,  "name": "Apple MacBook Air M2",        "price": "$1,099", "rating": "⭐ 4.9", "category": "Laptops",    "purpose": ["Office Work","Professional","Students"], "budget": 2000, "description": "Powerful and portable laptop for professionals and students"},
    {"id": 2,  "name": "Dell XPS 15",                 "price": "$999",   "rating": "⭐ 4.7", "category": "Laptops",    "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "High-performance laptop for professional work"},
    {"id": 3,  "name": "Lenovo ThinkPad X1 Carbon",   "price": "$899",   "rating": "⭐ 4.8", "category": "Laptops",    "purpose": ["Office Work","Travel"],                  "budget": 1000, "description": "Lightweight and durable business laptop"},
    {"id": 4,  "name": "Acer Aspire 5",               "price": "$399",   "rating": "⭐ 4.4", "category": "Laptops",    "purpose": ["Students","Office Work"],                "budget": 500,  "description": "Budget-friendly laptop for everyday use"},
    {"id": 5,  "name": "ASUS ROG Strix G16",          "price": "$1,299", "rating": "⭐ 4.8", "category": "Laptops",    "purpose": ["Gaming"],                               "budget": 2000, "description": "High-end gaming laptop with RTX graphics"},
    {"id": 6,  "name": "HP Pavilion 15",              "price": "$549",   "rating": "⭐ 4.3", "category": "Laptops",    "purpose": ["Students","Office Work","Travel"],       "budget": 1000, "description": "Versatile laptop for work and entertainment"},
    {"id": 7,  "name": "Microsoft Surface Laptop 5",  "price": "$999",   "rating": "⭐ 4.6", "category": "Laptops",    "purpose": ["Office Work","Professional"],            "budget": 1000, "description": "Premium ultrabook with touchscreen"},
    {"id": 8,  "name": "Sony WH-1000XM5",             "price": "$299",   "rating": "⭐ 4.9", "category": "Headphones", "purpose": ["Office Work","Travel","Professional"],   "budget": 300,  "description": "Noise-cancelling headphones with great sound quality"},
    {"id": 9,  "name": "Apple AirPods Pro 2",         "price": "$249",   "rating": "⭐ 4.8", "category": "Headphones", "purpose": ["Travel","Office Work"],                  "budget": 300,  "description": "Premium wireless earbuds with ANC"},
    {"id": 10, "name": "SteelSeries Arctis Nova Pro", "price": "$149",   "rating": "⭐ 4.7", "category": "Headphones", "purpose": ["Gaming"],                               "budget": 300,  "description": "Professional gaming headset"},
    {"id": 11, "name": "Anker Soundcore Q45",         "price": "$59",    "rating": "⭐ 4.5", "category": "Headphones", "purpose": ["Students","Travel"],                     "budget": 100,  "description": "Affordable noise-cancelling earbuds"},
    {"id": 12, "name": "Bose QuietComfort 45",        "price": "$229",   "rating": "⭐ 4.7", "category": "Headphones", "purpose": ["Travel","Office Work"],                  "budget": 300,  "description": "Premium noise-cancelling headphones"},
    {"id": 13, "name": "iPhone 15 Pro",               "price": "$999",   "rating": "⭐ 4.9", "category": "Phones",     "purpose": ["Professional","Travel"],                 "budget": 1000, "description": "Latest flagship smartphone with advanced camera"},
    {"id": 14, "name": "Samsung Galaxy S24",          "price": "$799",   "rating": "⭐ 4.8", "category": "Phones",     "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "Powerful Android phone with great display"},
    {"id": 15, "name": "Google Pixel 8a",             "price": "$499",   "rating": "⭐ 4.7", "category": "Phones",     "purpose": ["Students","Office Work","Travel"],       "budget": 500,  "description": "Affordable Google phone with excellent camera"},
    {"id": 16, "name": "Sony ZV-E10",                 "price": "$598",   "rating": "⭐ 4.7", "category": "Cameras",    "purpose": ["Professional","Travel"],                 "budget": 1000, "description": "Compact mirrorless camera for creators"},
    {"id": 17, "name": "Canon EOS Rebel SL3",         "price": "$649",   "rating": "⭐ 4.6", "category": "Cameras",    "purpose": ["Students","Travel"],                     "budget": 1000, "description": "Beginner-friendly DSLR camera"},
    {"id": 18, "name": "GoPro HERO12 Black",          "price": "$349",   "rating": "⭐ 4.7", "category": "Cameras",    "purpose": ["Travel","Gaming"],                       "budget": 500,  "description": "Action camera for adventure and vlogging"},
    {"id": 19, "name": "LG 27GP850-B",               "price": "$299",   "rating": "⭐ 4.8", "category": "Monitors",   "purpose": ["Gaming","Professional"],                 "budget": 300,  "description": "Gaming monitor with 144Hz refresh rate"},
    {"id": 20, "name": "Dell UltraSharp U2723DE",     "price": "$649",   "rating": "⭐ 4.9", "category": "Monitors",   "purpose": ["Professional","Office Work"],            "budget": 1000, "description": "Premium professional monitor"},
    {"id": 21, "name": "Samsung Odyssey G7",          "price": "$449",   "rating": "⭐ 4.7", "category": "Monitors",   "purpose": ["Gaming"],                               "budget": 500,  "description": "High-performance gaming monitor"},
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

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# Explicit routes for SEO files - must come BEFORE the catch-all route
@app.route('/robots.txt')
def robots():
    return send_from_directory('.', 'robots.txt', mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('.', 'sitemap.xml', mimetype='application/xml')

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
        "serpapi":       bool(SERPAPI_KEY),
        "affiliate":     bool(AMAZON_AFFILIATE),
        "affiliate_tag": AMAZON_AFFILIATE or None,
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
