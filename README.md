# demo-commerce-claude

A pipeline for sales engineers that turns any customer product page into a live, shareable WordPress Playground demo using Remote Data Blocks. Runs locally via CLI or triggered from GitHub Actions — no local setup required for teammates.

---

## What it does

1. **Scrapes** a customer's product page and extracts product data
2. **Maps** that data to a Remote Data Blocks schema, grouped by category
3. **Deploys** one mock JSON API endpoint per category to GitHub Pages
4. **Generates** a WordPress Playground blueprint with Remote Data Blocks pre-installed, the connector plugin pre-registered, and a shareable link

---

## Running via GitHub Actions (recommended for teams)

No local setup needed. From the repo:

**Actions → Build Demo → Run workflow**

Fill in:
- **Customer product page URL**
- **Demo slug** (e.g. `acme-spring-2025`)

The job summary will show all generated URLs when complete, including a one-click Playground link.

Requires one repo secret: `ANTHROPIC_API_KEY` (Settings → Secrets and variables → Actions).

---

## Running locally (CLI)

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

Creates the `gh-pages` branch if it doesn't exist. Then enable GitHub Pages in your repo settings: **Settings → Pages → Source: `gh-pages` branch, `/ (root)`**.

### Build a demo

```bash
uv run main.py build
```

You'll be prompted for a URL and slug. Output:

```
Mock API endpoints
  [all]      https://your-username.github.io/your-repo/demos/acme-spring-2025/data.json
  [travel]   https://your-username.github.io/your-repo/demos/acme-spring-2025/data-travel.json
  [outdoor]  https://your-username.github.io/your-repo/demos/acme-spring-2025/data-outdoor.json

Blueprint   https://your-username.github.io/your-repo/demos/acme-spring-2025/blueprint.json
Playground  https://playground.wordpress.net/?blueprint-url=...
```

Share the **Playground** link. When opened, it launches a pre-configured WordPress instance with Remote Data Blocks installed and every category registered as its own insertable block.

---

## How it works under the hood

### Stage 1 — Scraping (`stages/scraper.py`)

Fetches the customer URL with `requests` and parses it with BeautifulSoup. Product extraction is handled by Claude (Anthropic API), with the input optimised to keep token usage low:

**JSON-LD first (preferred path)**
Most modern e-commerce sites embed structured data as `<script type="application/ld+json">` tags — schema.org markup added for SEO. It contains clean, labelled product data (name, price, SKU, image, description) without HTML noise. When found, only this is sent to Claude (~8k chars max).

**Plain text fallback**
If no JSON-LD is present, all HTML tags are stripped and compact plain text is sent (~15k chars). Claude infers products from patterns — currency symbols, "add to cart" language, repeated name/price groupings. Less reliable on heavily JS-rendered pages where the server returns an empty shell.

**What counts as a product**
No hardcoded rules — Claude interprets the content. Flexible across site structures but results on unusual pages may need a second pass. Output is capped at 50 items with descriptions truncated to 150 characters.

---

### Stage 2 — Schema mapping & category splitting (`stages/mapper.py`)

Claude takes the extracted products and generates:

- **`categories`** — products grouped by detected category (e.g. `all`, `travel`, `outdoor-gear`). The `all` key always contains every product. Limited to 6 categories max.
- **`output_schema`** — a Remote Data Blocks field map using JSONPath expressions and appropriate RDB field types (`string`, `image_url`, `url`, `id`, etc.)
- **`php_plugin_code`** — a complete WordPress plugin that registers one `register_remote_data_block()` call per category, each pointing to its own endpoint via a `%%ENDPOINT_{key}%%` placeholder

The RDB registration pattern used:

```php
function register_demo_blocks() {
    $output_schema = [
        'is_collection' => true,
        'type' => [
            'id'    => ['name' => 'ID',    'path' => '$.id',    'type' => 'id'],
            'name'  => ['name' => 'Name',  'path' => '$.name',  'type' => 'string'],
            'price' => ['name' => 'Price', 'path' => '$.price', 'type' => 'string'],
        ],
    ];

    register_remote_data_block([
        'title'        => 'Demo Products — All',
        'render_query' => [
            'query' => [
                'display_name'  => 'Get All Products',
                'data_source'   => ['display_name' => 'Demo Products', 'endpoint' => 'https://...data.json'],
                'output_schema' => $output_schema,
            ],
        ],
    ]);

    register_remote_data_block([
        'title'        => 'Demo Products — Travel',
        'render_query' => [
            'query' => [
                'display_name'  => 'Get Travel Products',
                'data_source'   => ['display_name' => 'Demo Products', 'endpoint' => 'https://...data-travel.json'],
                'output_schema' => $output_schema,
            ],
        ],
    ]);
}
add_action('init', 'register_demo_blocks', 10, 0);
```

Endpoint placeholders (`%%ENDPOINT_all%%`, `%%ENDPOINT_travel%%`, etc.) are replaced with real GitHub Pages URLs after deployment.

**Why no input schema?**
Filtering is handled at build time — each category has its own static endpoint that always returns the right subset. There is nothing to pass as a query parameter, so no input schema is needed.

---

### Stage 3 — GitHub Pages deployment (`stages/api_host.py`)

Pushes files to the `gh-pages` branch via the GitHub Contents API:

- `demos/{slug}/data.json` — all products
- `demos/{slug}/data-{category}.json` — one file per detected category
- `demos/{slug}/blueprint.json` — the Playground blueprint

GitHub Pages serves all files with `Access-Control-Allow-Origin: *` by default, so WordPress Playground can fetch them cross-origin with no CORS configuration. If the `gh-pages` branch doesn't exist, it's created automatically from the default branch HEAD.

---

### Stage 4 — Playground blueprint (`stages/blueprint.py`)

Generates a `blueprint.json` that tells WordPress Playground how to configure itself on load:

1. Install Remote Data Blocks from wordpress.org
2. Create the `demo-connector` plugin directory
3. Write the generated connector plugin file
4. Activate the connector plugin
5. Set the site name to the demo title
6. Log in as admin and land on the block editor

The Playground URL uses `?blueprint-url=` pointing to the hosted blueprint file rather than encoding the blueprint in the URL hash — no length limits, stable URL, re-runnable with the same slug to update.

---

## Limitations & known edge cases

| Situation | Behaviour |
|---|---|
| JS-rendered page (React, Vue) | Scraper sees little content — may return few or no products |
| No JSON-LD, dense HTML | Falls back to plain text extraction — less precise |
| Page behind a login | Request will fail or return a login page |
| Large product catalogue (50+ items) | Capped at 50 items per run |
| No clear categories detected | Returns `all` key only — single block registered |
| RDB PHP API changes | Generated plugin code may need minor edits if RDB updates its registration API |

---

## File structure

```
demo-commerce-claude/
├── .github/
│   └── workflows/
│       └── build-demo.yml    # GHA workflow — trigger from GitHub UI
├── .env                      # your credentials (not committed)
├── .env.example              # template
├── .gitignore
├── pyproject.toml            # dependencies for uv
├── requirements.txt
├── config.py                 # reads env vars
├── main.py                   # CLI (build, setup commands) + GHA summary output
└── stages/
    ├── scraper.py            # Stage 1: fetch + extract products
    ├── mapper.py             # Stage 2: category split + RDB schema + PHP plugin
    ├── api_host.py           # Stage 3: deploy per-category JSON to GitHub Pages
    └── blueprint.py          # Stage 4: compose Playground blueprint
```
