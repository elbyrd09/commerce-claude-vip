import os
import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

import config
from stages.scraper import scrape_products
from stages.mapper import map_to_rdb_schema
from stages.api_host import deploy_data, deploy_blueprint
from stages.blueprint import generate_blueprint, playground_url

console = Console()

IN_GHA = os.environ.get("GITHUB_ACTIONS") == "true"


def _validate_config() -> None:
    missing = [k for k in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GITHUB_PAGES_REPO") if not getattr(config, k)]
    if missing:
        console.print(f"[red]Missing required env vars: {', '.join(missing)}[/red]")
        console.print("[dim]Copy .env.example to .env and fill in the values.[/dim]")
        sys.exit(1)


def _write_gha_summary(lines: list[str]) -> None:
    """Write output to the GitHub Actions job summary if running in GHA."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("\n".join(lines) + "\n")


@click.group()
def cli():
    """RDB Demo Builder — turn any product page into a live WordPress Playground demo."""


@cli.command()
@click.option("--url", prompt="Customer product page URL", help="URL of the product page to scrape")
@click.option("--slug", prompt="Demo slug (e.g. acme-spring-2025)", help="Short ID used in the hosted file path")
def build(url: str, slug: str) -> None:
    """Scrape a product page, build a mock API, and generate a shareable Playground link."""
    _validate_config()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:

        t = progress.add_task("[cyan]1/4  Scraping product page…", total=None)
        products = scrape_products(url)
        count = len(products["items"])
        title = products.get("page_title", "page")
        progress.update(t, description=f"[green]1/4  Found {count} products from {title}")

        t = progress.add_task("[cyan]2/4  Mapping to RDB schema…", total=None)
        schema = map_to_rdb_schema(products, url)
        categories = schema["categories"]
        cat_names = [k for k in categories.keys() if k != "all"]
        progress.update(t, description=f"[green]2/4  Schema mapped  →  {schema['demo_title']}  ({len(cat_names)} categories)")

        t = progress.add_task("[cyan]3/4  Deploying mock API…", total=None)
        endpoint_urls = deploy_data(categories, slug)
        progress.update(t, description=f"[green]3/4  {len(endpoint_urls)} endpoints live")

        # Inject real endpoint URLs into the PHP plugin code
        php_code = schema["php_plugin_code"]
        for cat_key, url_ in endpoint_urls.items():
            php_code = php_code.replace(f"%%ENDPOINT_{cat_key}%%", url_)

        t = progress.add_task("[cyan]4/4  Building Playground blueprint…", total=None)
        bp = generate_blueprint(
            php_plugin_code=php_code,
            demo_title=schema["demo_title"],
            block_slug=schema["block_slug"],
        )
        bp_url = deploy_blueprint(bp, slug)
        pg_url = playground_url(bp_url)
        progress.update(t, description="[green]4/4  Blueprint deployed")

    # --- Output ---
    api_lines = "\n".join(
        f"  [{k}]  {u}" for k, u in endpoint_urls.items()
    )

    console.print(
        Panel.fit(
            f"[bold green]Demo ready![/bold green]\n\n"
            f"[bold]Mock API endpoints[/bold]\n{api_lines}\n\n"
            f"[bold]Blueprint[/bold]   {bp_url}\n\n"
            f"[bold]Playground[/bold]  {pg_url}",
            title="[bold]RDB Demo Builder[/bold]",
            border_style="green",
        )
    )
    console.print(
        f"\n[dim]Open the Playground link and insert any "
        f"[bold]{schema['demo_title']}[/bold] block from the block inserter "
        f"to see category-filtered data.[/dim]"
    )

    # Write a clean summary to GitHub Actions job UI if running in GHA
    if IN_GHA:
        _write_gha_summary([
            f"## Demo ready — {schema['demo_title']}",
            "",
            "### Mock API endpoints",
            *[f"- **{k}**: {u}" for k, u in endpoint_urls.items()],
            "",
            f"### Blueprint",
            f"{bp_url}",
            "",
            f"### Playground",
            f"[Open demo]({pg_url})",
        ])


@cli.command()
def setup() -> None:
    """Check configuration and ensure the GitHub Pages branch exists."""
    _validate_config()

    from stages.api_host import ensure_branch

    owner, repo = config.GITHUB_PAGES_REPO.split("/", 1)
    branch = config.GITHUB_PAGES_BRANCH

    console.print(f"Checking [bold]{owner}/{repo}[/bold] branch [bold]{branch}[/bold]…")
    try:
        ensure_branch(owner, repo, branch)
        console.print("[green]Branch ready.[/green]")
    except Exception as exc:
        console.print(f"[red]Failed: {exc}[/red]")
        sys.exit(1)

    pages_url = f"https://{owner}.github.io/{repo}/"
    console.print(
        f"\n[bold]Next step:[/bold] enable GitHub Pages in your repo settings "
        f"(Settings → Pages → Source: branch [bold]{branch}[/bold], folder [bold]/ (root)[/bold]).\n"
        f"Your demo APIs will be hosted under: [bold]{pages_url}demos/[/bold]"
    )


if __name__ == "__main__":
    cli()
