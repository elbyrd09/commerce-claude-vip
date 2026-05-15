import json
import requests
from bs4 import BeautifulSoup
import anthropic
import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


_SYSTEM = """\
You are a data extraction specialist. Extract all product listings from a commerce page.

Return ONLY valid JSON with this structure:
{
  "page_title": "brand or page name",
  "items": [
    {
      "id": "sku, product ID, or sequential number as string",
      "name": "product name",
      "description": "description or null",
      "price": "price with currency symbol, or null",
      "image_url": "absolute URL only, or null",
      "url": "product page URL or null",
      "category": "category or null"
    }
  ],
  "detected_fields": ["name", "price", "...all field names found"]
}

Rules:
- Include ALL extra fields present (brand, rating, stock, sku, etc.) as additional keys on each item
- Only include absolute image URLs — skip relative paths
- If the page uses JavaScript rendering and you see little/no product data, still return whatever is visible
- Keep descriptions under 150 characters — truncate if needed
- Cap at 50 items maximum if the page has more
- Return ONLY the JSON object, no markdown fences or explanation\
"""


def scrape_products(url: str) -> dict:
    """Fetch a customer product page and extract structured product data via Claude."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DemoBuilder/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Collect JSON-LD structured data first — it's usually server-rendered and reliable
    json_ld_blocks = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            json_ld_blocks.append(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            pass

    # Strip noise
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.decompose()

    user_parts = []

    if json_ld_blocks:
        # JSON-LD is already structured — prefer it and skip sending raw HTML
        user_parts.append(
            "Structured data (JSON-LD):\n"
            + json.dumps(json_ld_blocks, indent=2)[:8_000]
        )
    else:
        # Fall back to compact plain text (much smaller than raw HTML)
        text = " ".join(soup.get_text(" ", strip=True).split())[:15_000]
        user_parts.append(f"Page text:\n{text}")

    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "\n\n---\n\n".join(user_parts)}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    return json.loads(raw)
