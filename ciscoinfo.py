"""
cisco_info_page.py
------------------
Fetches public information from Cisco product pages and builds a browsable
HTML page (cisco_products.html).

Install:  pip install requests beautifulsoup4
Run:      python cisco_info_page.py

Design rules (to avoid wrong data):
  * Only text that is actually found on the fetched page is shown.
  * If something is not found, the page says "Not found on page" - nothing is guessed.
  * robots.txt is checked before every request, and requests are rate-limited.
  * Every item links back to its source URL so you can verify it.

For personal study use. Check Cisco's website terms before any other use.
"""

import re
import time
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# CONFIG - add or remove Cisco product page URLs here
# ----------------------------------------------------------------------------
PRODUCT_URLS = [
    "https://www.cisco.com/c/en/us/products/switches/catalyst-9300-series-switches/index.html",
    "https://www.cisco.com/c/en/us/products/switches/catalyst-9200-series-switches/index.html",
    "https://www.cisco.com/c/en/us/products/switches/catalyst-9500-series-switches/index.html",
]

# Cisco's central end-of-life listing (shown as a reference link on the page)
EOS_LISTING_URL = "https://www.cisco.com/c/en/us/products/eos-eol-listing.html"

USER_AGENT = "Mozilla/5.0 (compatible; StudyScraper/1.0; personal learning project)"
REQUEST_DELAY_SECONDS = 2
TIMEOUT_SECONDS = 20
MAX_IMAGES_PER_PRODUCT = 4
OUTPUT_DIR = Path("cisco_output")
IMAGE_DIR = OUTPUT_DIR / "images"

NOT_FOUND = "Not found on page"
PRICE_RE = re.compile(r"(?:US\$|USD\s?|\$|₹|Rs\.?\s?|€|£)\s?\d[\d,]*(?:\.\d{1,2})?")
EOS_RE = re.compile(r"end[\s\-_]*of[\s\-_]*(sale|life|support)|\beos\b|\beol\b", re.I)

ROBOT_AGENT = "StudyScraper"  # the name robots.txt rules are matched against

# Optional offline mode: if you save a Cisco page from your own browser
# (Ctrl+S -> "Webpage, HTML only"), map its URL to the saved file here and the
# script will parse that file instead of requesting the page.
LOCAL_HTML = {
    # "https://www.cisco.com/c/en/us/products/switches/catalyst-9300-series-switches/index.html":
    #     "saved_pages/catalyst_9300.html",
}

_robots_cache = {}


# ----------------------------------------------------------------------------
# Fetching
# ----------------------------------------------------------------------------
def load_robots(base):
    """Download and parse robots.txt ourselves, sending a proper User-Agent.

    Python's built-in RobotFileParser.read() uses a default 'Python-urllib'
    User-Agent. Many sites answer that with HTTP 403, and the parser then
    treats the whole site as disallowed - a false 'blocked' result. Fetching
    the file with requests avoids that.
    Returns (parser_or_None, note).
    """
    try:
        r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return None, f"could not download robots.txt ({exc})"
    rp = RobotFileParser()
    if r.status_code == 200:
        rp.parse(r.text.splitlines())
        return rp, "robots.txt loaded"
    if r.status_code in (404, 410):
        rp.parse([])  # no robots.txt published = no restrictions
        return rp, "no robots.txt published"
    return None, f"robots.txt request returned HTTP {r.status_code}"


def allowed_by_robots(url):
    """Return (allowed, reason)."""
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        _robots_cache[base] = load_robots(base)
    rp, note = _robots_cache[base]
    if rp is None:
        return False, note
    if rp.can_fetch(ROBOT_AGENT, url):
        return True, note
    return False, "the site's robots.txt disallows this URL for automated tools"


def fetch(url):
    """Return (html, error). Exactly one of them is None."""
    local = LOCAL_HTML.get(url)
    if local and Path(local).exists():
        print("  using saved file", local)
        return Path(local).read_text(encoding="utf-8", errors="ignore"), None
    ok, why = allowed_by_robots(url)
    if not ok:
        return None, (
            f"Not fetched: {why}. To include this page, open it in your browser, save it "
            f"as HTML, and add it to LOCAL_HTML at the top of this script."
        )
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return None, f"Network error: {exc}"
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code} returned by server."
    return resp.text, None


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------
def meta_content(soup, *names):
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content", "").strip():
            return tag["content"].strip()
    return None


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_product(url, html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = meta_content(soup, "og:title") or (clean(soup.h1.get_text()) if soup.h1 else None)
    description = meta_content(soup, "og:description", "description")

    # Functionality: list items / paragraphs of reasonable length from the main content
    root = soup.find("main") or soup.body or soup
    points, seen = [], set()
    for el in root.find_all(["li", "p"]):
        text = clean(el.get_text(" "))
        if 40 <= len(text) <= 300 and text not in seen:
            seen.add(text)
            points.append(text)
        if len(points) >= 8:
            break

    # EOS / EOL links actually present on the page
    eos_links, seen_links = [], set()
    for a in root.find_all("a", href=True):
        label = clean(a.get_text(" "))
        href = urljoin(url, a["href"])
        if (EOS_RE.search(label) or EOS_RE.search(href)) and href not in seen_links:
            seen_links.add(href)
            eos_links.append((label or href, href))

    # Pricing: only amounts literally present in the page text
    page_text = clean(root.get_text(" "))
    price_hits = []
    for m in PRICE_RE.finditer(page_text):
        start = max(0, m.start() - 60)
        snippet = page_text[start : m.end() + 60]
        price_hits.append((m.group(0), snippet))
        if len(price_hits) >= 5:
            break

    # Images: og:image first, then product images in the page
    images, seen_imgs = [], set()
    og = meta_content(soup, "og:image")
    candidates = ([og] if og else []) + [i.get("src") for i in root.find_all("img") if i.get("src")]
    for src in candidates:
        full = urljoin(url, src)
        if full in seen_imgs or full.lower().endswith((".svg", ".gif")):
            continue
        if src is not og and "/content/dam/" not in full:
            continue  # skip icons / tracking pixels
        seen_imgs.add(full)
        images.append(full)
        if len(images) >= MAX_IMAGES_PER_PRODUCT:
            break

    return {
        "url": url,
        "title": title or NOT_FOUND,
        "description": description or NOT_FOUND,
        "points": points,
        "eos_links": eos_links,
        "prices": price_hits,
        "images": images,
    }


def download_images(product, index):
    """Download images next to the report. Falls back to the remote URL on failure."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for n, img_url in enumerate(product["images"], start=1):
        ext = Path(urlparse(img_url).path).suffix.lower() or ".jpg"
        local = IMAGE_DIR / f"product{index}_{n}{ext}"
        if not allowed_by_robots(img_url)[0]:
            result.append(img_url)  # don't download; the browser will load it from Cisco directly
            continue
        try:
            r = requests.get(img_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
                local.write_bytes(r.content)
                result.append(local.relative_to(OUTPUT_DIR).as_posix())
                time.sleep(0.5)
                continue
        except requests.RequestException:
            pass
        result.append(img_url)  # remote fallback
    product["image_srcs"] = result


# ----------------------------------------------------------------------------
# HTML output
# ----------------------------------------------------------------------------
CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#f3f6fa;margin:0;color:#1f2933}
header{background:#049fd9;color:#fff;padding:28px 40px}
header h1{margin:0 0 6px}
nav{background:#fff;padding:12px 40px;border-bottom:1px solid #dde3ea;position:sticky;top:0}
nav a{margin-right:18px;color:#0b5c80;text-decoration:none;font-weight:600}
main{max-width:1000px;margin:24px auto;padding:0 20px}
.card{background:#fff;border-radius:12px;padding:24px;margin-bottom:28px;box-shadow:0 3px 12px rgba(0,0,0,.07)}
.card h2{margin-top:0}
.gallery{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
.gallery img{height:150px;border:1px solid #e1e6ec;border-radius:8px;background:#fff;padding:4px}
h3{margin:18px 0 6px;color:#0b5c80}
.missing{color:#8a6d00;background:#fff8dc;padding:6px 10px;border-radius:6px;display:inline-block}
.err{color:#9b1c1c;background:#fde8e8;padding:10px;border-radius:6px}
table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #e5e9ee;padding:8px;text-align:left;vertical-align:top}
th{background:#f0f4f8}
footer{text-align:center;color:#6b7785;font-size:13px;padding:20px}
"""


def render_product(p, idx):
    parts = [f'<section class="card" id="p{idx}">']
    parts.append(f"<h2>{escape(p['title'])}</h2>")
    parts.append(f'<p>Source: <a href="{escape(p["url"])}" target="_blank" rel="noopener">{escape(p["url"])}</a></p>')

    if p.get("image_srcs"):
        imgs = "".join(f'<img src="{escape(s)}" alt="{escape(p["title"])}" loading="lazy">' for s in p["image_srcs"])
        parts.append(f'<div class="gallery">{imgs}</div>')
    else:
        parts.append(f'<p class="missing">Pictures: {NOT_FOUND}</p>')

    parts.append("<h3>Overview / functionality</h3>")
    if p["description"] != NOT_FOUND:
        parts.append(f"<p>{escape(p['description'])}</p>")
    if p["points"]:
        parts.append("<ul>" + "".join(f"<li>{escape(t)}</li>" for t in p["points"]) + "</ul>")
    elif p["description"] == NOT_FOUND:
        parts.append(f'<p class="missing">{NOT_FOUND}</p>')

    parts.append("<h3>End-of-Sale / End-of-Life (EOS / EOL)</h3>")
    if p["eos_links"]:
        parts.append("<ul>" + "".join(
            f'<li><a href="{escape(h)}" target="_blank" rel="noopener">{escape(t)}</a></li>' for t, h in p["eos_links"]
        ) + "</ul>")
    else:
        parts.append(
            f'<p class="missing">No EOS/EOL notice linked on this page.</p> '
            f'<a href="{escape(EOS_LISTING_URL)}" target="_blank" rel="noopener">Check Cisco\'s official EOS/EOL listing</a>'
        )

    parts.append("<h3>Pricing</h3>")
    if p["prices"]:
        rows = "".join(f"<tr><td>{escape(a)}</td><td>...{escape(s)}...</td></tr>" for a, s in p["prices"])
        parts.append(f"<table><tr><th>Amount found</th><th>Context on page</th></tr>{rows}</table>")
    else:
        parts.append(
            '<p class="missing">No price is published on this page. Cisco list prices are normally '
            "available only through Cisco Commerce / authorized partners.</p>"
        )
    parts.append("</section>")
    return "\n".join(parts)


def render_page(products, errors):
    nav = "".join(f'<a href="#p{i}">{escape(p["title"][:40])}</a>' for i, p in enumerate(products, 1))
    body = "\n".join(render_product(p, i) for i, p in enumerate(products, 1))
    err_html = ""
    if errors:
        items = "".join(f"<li><b>{escape(u)}</b><br>{escape(e)}</li>" for u, e in errors)
        err_html = f'<section class="card"><h2>Pages that could not be fetched</h2><div class="err"><ul>{items}</ul></div></section>'
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cisco Product Information</title><style>{CSS}</style></head>
<body>
<header><h1>Cisco Product Information</h1><div>Data collected from public Cisco pages on {now}</div></header>
<nav>{nav}</nav>
<main>{body}{err_html}</main>
<footer>Information is copied from the linked Cisco pages. Always verify on cisco.com. Images belong to Cisco.</footer>
</body></html>"""


# ----------------------------------------------------------------------------
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    products, errors = [], []
    for url in PRODUCT_URLS:
        print("Fetching", url)
        html, err = fetch(url)
        if err:
            print("  ->", err)
            errors.append((url, err))
        else:
            product = parse_product(url, html)
            download_images(product, len(products) + 1)
            products.append(product)
        time.sleep(REQUEST_DELAY_SECONDS)

    out = OUTPUT_DIR / "cisco_products.html"
    out.write_text(render_page(products, errors), encoding="utf-8")
    print("Created", out.resolve())
    webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()