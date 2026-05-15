# demo-commerce-claude

A CLI tool for sales engineers that turns any customer product page into a live, shareable WordPress Playground demo using Remote Data Blocks.

---

## What it does

1. **Scrapes** a customer's product page and extracts product data
2. **Maps** that data to a Remote Data Blocks input/output schema
3. **Deploys** a mock JSON API to GitHub Pages
4. **Generates** a WordPress Playground blueprint with Remote Data Blocks pre-installed and the data source pre-registered — outputs a shareable link

---

## Setup

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- An [Anthropic API key](https://console.anthropic.com/)
- A GitHub personal access token with `repo` scope
- A public GitHub repo with GitHub Pages enabled on the `gh-pages` branch

### Configuration

```bash
cp .env.example .env
```

Fill in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
GITHUB_PAGES_REPO=your-username/your-repo
GITHUB_PAGES_BRANCH=gh-pages   # default, can omit
```

### First-time branch setup

```bash
uv run main.py setup
```

This creates the `gh-pages` branch if it doesn't exist. Then go to your repo's **Settings → Pages** and set the source to the `gh-pages` branch, `/ (root)` folder.

---

## Usage

```bash
uv run main.py build
```

You'll be prompted for:
- **Customer product page URL** — the page you want to scrape
- **Demo slug** — a short identifier used in the hosted file path, e.g. `acme-spring-2025`

Output:

```
Mock API    https://your-username.github.io/your-repo/demos/acme-spring-2025/data.json
Blueprint   https://your-username.github.io/your-repo/demos/acme-spring-2025/blueprint.json
Playground  https://playground.wordpress.net/?blueprint-url=...
```

Share the **Playground** link with teammates. When opened, it launches a pre-configured WordPress instance with Remote Data Blocks installed and the data source ready to use. Open a new page in the block editor and insert the block from the inserter.

---

## How it works under the hood

### Stage 1 — Scraping (`stages/scraper.py`)

The tool fetches the customer URL with `requests` and parses it with BeautifulSoup. Product extraction uses Claude (Anthropic API), but the input is optimized in two ways:

**JSON-LD first (preferred path)**
Most modern e-commerce sites embed structured data in their HTML as `<script type="application/ld+json">` tags. This is schema.org markup added primarily for SEO — it contains clean, labeled product data (name, price, SKU, image, description) without any HTML noise. When JSON-LD is found, only that data is sent to Claude (~8k chars max), making the call fast and cheap.

**Plain text fallback**
If no JSON-LD is present, the tool strips all HTML tags and sends compact plain text to Claude (~15k chars). Claude infers products from patterns in the text — repeated structures, currency symbols, "add to cart" language, grouped name/price pairs, etc. This is less reliable than JSON-LD and may miss products on heavily JavaScript-rendered pages (where the server sends an empty shell and the browser builds the content).

**What counts as a product**
There is no hardcoded rule. Claude interprets the page content and decides what looks like a product. This makes the tool flexible across different site structures, but it means results on unusual pages may need a second pass.

Output is capped at 50 items with descriptions truncated to 150 characters to stay within token limits.

### Stage 2 — Schema mapping (`stages/mapper.py`)

Claude takes the extracted products and generates three things:

- **`json_data`** — a normalized JSON array of all products, used as the mock API payload
- **`output_schema`** — a Remote Data Blocks field map using JSONPath expressions (e.g. `$.name`, `$.price`) and appropriate RDB field types (`string`, `image_url`, `url`, `id`, etc.)
- **`php_plugin_code`** — a complete WordPress plugin PHP file that registers the data source and block using `register_remote_data_block()`

The RDB registration pattern used:

```php
function register_demo_block() {
    $data_source = [
        'display_name' => 'Demo Products',
        'endpoint'     => 'https://your-api-url/data.json',
    ];

    $render_query = [
        'display_name'  => 'Get Products',
        'data_source'   => $data_source,
        'output_schema' => [
            'is_collection' => true,
            'type' => [
                'id'    => ['name' => 'ID',    'path' => '$.id',    'type' => 'id'],
                'name'  => ['name' => 'Name',  'path' => '$.name',  'type' => 'string'],
                'price' => ['name' => 'Price', 'path' => '$.price', 'type' => 'string'],
            ],
        ],
    ];

    register_remote_data_block([
        'title'        => 'Demo Products',
        'render_query' => ['query' => $render_query],
    ]);
}
add_action('init', 'register_demo_block', 10, 0);
```

The endpoint URL is injected at deploy time using a `%%ENDPOINT_URL%%` placeholder.

### Stage 3 — GitHub Pages deployment (`stages/api_host.py`)

Two files are pushed to the `gh-pages` branch via the GitHub Contents API:

- `demos/{slug}/data.json` — the mock API payload
- `demos/{slug}/blueprint.json` — the Playground blueprint

GitHub Pages serves both with `Access-Control-Allow-Origin: *` by default, so WordPress Playground can fetch them cross-origin without any CORS configuration.

If the `gh-pages` branch doesn't exist, the tool creates it automatically from the default branch HEAD.

### Stage 4 — Playground blueprint (`stages/blueprint.py`)

The blueprint is a JSON file that tells WordPress Playground how to configure itself. Steps executed on load:

1. Install Remote Data Blocks from wordpress.org (v1.4.3+)
2. Write the generated connector plugin to the virtual filesystem
3. Activate the connector plugin
4. Set the site name to match the demo title
5. Log in as admin

The Playground URL uses the `?blueprint-url=` parameter pointing to the hosted blueprint file, rather than encoding the blueprint in the URL hash. This avoids URL length limits and gives you a stable link you can update by re-running the tool with the same slug.

---

## Limitations & known edge cases

| Situation | Behaviour |
|---|---|
| JS-rendered page (React, Vue) | Scraper sees little content — may return few or no products |
| No JSON-LD, dense HTML | Falls back to plain text extraction — less precise |
| Page behind a login | Request will fail or return a login page |
| Large product catalogue (50+ items) | Capped at 50 items per run |
| RDB PHP API changes | Generated plugin code may need minor edits if RDB updates its registration API |

---

## File structure

```
demo-commerce-claude/
├── .env                  # your credentials (not committed)
├── .env.example          # template
├── pyproject.toml        # dependencies for uv
├── requirements.txt
├── config.py             # reads env vars
├── main.py               # CLI (build, setup commands)
└── stages/
    ├── scraper.py        # Stage 1: fetch + extract
    ├── mapper.py         # Stage 2: RDB schema + PHP plugin
    ├── api_host.py       # Stage 3: GitHub Pages deployment
    └── blueprint.py      # Stage 4: Playground blueprint
```
