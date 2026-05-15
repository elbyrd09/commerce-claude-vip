import json
import anthropic
import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


_RDB_REFERENCE = """\
## Remote Data Blocks — PHP Registration Pattern (multi-category)

```php
function register_example_blocks() {
    // Define output schema once and reuse across all queries
    $output_schema = [
        'is_collection' => true,
        'type' => [
            'id'    => [ 'name' => 'ID',    'path' => '$.id',    'type' => 'id'     ],
            'title' => [ 'name' => 'Title', 'path' => '$.title', 'type' => 'string' ],
            'price' => [ 'name' => 'Price', 'path' => '$.price', 'type' => 'string' ],
        ],
    ];

    // One register_remote_data_block() call per category, each with its own endpoint
    register_remote_data_block([
        'title'        => 'Example Items — All',
        'render_query' => [
            'query' => [
                'display_name'  => 'Get All Items',
                'data_source'   => [ 'display_name' => 'Example API', 'endpoint' => '%%ENDPOINT_all%%' ],
                'output_schema' => $output_schema,
            ],
        ],
    ]);

    register_remote_data_block([
        'title'        => 'Example Items — Travel',
        'render_query' => [
            'query' => [
                'display_name'  => 'Get Travel Items',
                'data_source'   => [ 'display_name' => 'Example API', 'endpoint' => '%%ENDPOINT_travel%%' ],
                'output_schema' => $output_schema,
            ],
        ],
    ]);
}
add_action( 'init', 'register_example_blocks', 10, 0 );
```

## Output Schema Field Types
string, id, integer, number, boolean, url, image_url, image_alt,
email_address, html, markdown, button_url, null, uuid

## Endpoint Placeholders
Each category uses its own placeholder: %%ENDPOINT_all%%, %%ENDPOINT_{category-slug}%%
These are replaced with real GitHub Pages URLs after deployment.\
"""

_INSTRUCTION = """\
Given product data extracted from a customer website, produce everything needed to demo
Remote Data Blocks with per-category filtering — one block registered per category.

Return ONLY valid JSON with these exact keys:
{
  "demo_title":    "human-readable label, e.g. 'Acme Products'",
  "block_slug":    "lowercase-hyphenated slug, e.g. 'acme-products'",
  "output_schema": { "is_collection": true, "type": { ...RDB field map... } },
  "categories": {
    "all":           [ ...every product, normalized... ],
    "category-slug": [ ...products in that category... ],
    ...one key per detected category...
  },
  "php_plugin_code": "complete PHP plugin file as a string"
}

Rules for categories:
- "all" key is always required and contains every product
- Detect natural categories from the data (category field, product type, tags, etc.)
- If no clear categories exist, return only the "all" key
- Category keys must be lowercase hyphenated slugs (e.g. "travel", "outdoor-gear")
- Normalize all product field names to snake_case
- Every product must have an "id" field
- Keep descriptions under 150 characters
- Limit to 6 categories maximum

Rules for output_schema:
- Map every useful field (name, price, description, image, url, category, etc.)
- Use image_url for images, url/button_url for links, string for text/price, id for IDs
- Paths like $.field_name reference keys within each JSON array item

Rules for php_plugin_code:
- Plugin header: Plugin Name, Description, Version 1.0.0
- Define $output_schema once at the top of the function and reuse across all queries
- One register_remote_data_block() call per category key in the categories object
- Block titles formatted as "{demo_title} — {Human Readable Category Name}"
- Endpoint placeholders: %%ENDPOINT_all%%, %%ENDPOINT_{category-slug}%%
- Single function + add_action('init') — no class-based approach
- No trailing ?> tag\
"""


def map_to_rdb_schema(products: dict, source_url: str) -> dict:
    """Map extracted products to RDB schema, grouped by category for per-category blocks."""
    sample = products["items"][:5]
    all_items = products["items"]

    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _RDB_REFERENCE,
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": _INSTRUCTION},
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Source URL: {source_url}\n"
                    f"Page title: {products.get('page_title', 'Unknown')}\n"
                    f"Detected fields: {products.get('detected_fields', [])}\n"
                    f"Total products: {len(all_items)}\n\n"
                    f"Sample (up to 5 items):\n{json.dumps(sample, indent=2)}\n\n"
                    f"All items:\n{json.dumps(all_items, indent=2)}"
                ),
            }
        ],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    return json.loads(raw)
