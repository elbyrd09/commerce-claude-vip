import base64
import json
import requests
import config

GITHUB_API = "https://api.github.com"


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _push_file(owner: str, repo: str, branch: str, path: str, content: str, message: str) -> None:
    headers = _auth_headers()
    encoded = base64.b64encode(content.encode()).decode()
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"

    existing = requests.get(url, headers=headers, params={"ref": branch})
    payload: dict = {"message": message, "content": encoded, "branch": branch}
    if existing.status_code == 200:
        payload["sha"] = existing.json()["sha"]

    resp = requests.put(url, headers=headers, json=payload)
    resp.raise_for_status()


def ensure_branch(owner: str, repo: str, branch: str) -> None:
    """Create the gh-pages branch from the default branch HEAD if it doesn't exist."""
    headers = _auth_headers()

    # Check if branch already exists
    check = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}", headers=headers)
    if check.status_code == 200:
        return

    # Get default branch SHA
    repo_info = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
    repo_info.raise_for_status()
    default_branch = repo_info.json()["default_branch"]

    ref_resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{default_branch}",
        headers=headers,
    )
    ref_resp.raise_for_status()
    sha = ref_resp.json()["object"]["sha"]

    create_resp = requests.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{branch}", "sha": sha},
    )
    if create_resp.status_code not in (201, 422):  # 422 = already exists, race condition safe
        create_resp.raise_for_status()


def deploy_data(categories: dict, slug: str) -> dict:
    """Push one JSON file per category to GitHub Pages. Returns {category_key: url}."""
    owner, repo = config.GITHUB_PAGES_REPO.split("/", 1)
    branch = config.GITHUB_PAGES_BRANCH

    ensure_branch(owner, repo, branch)

    endpoint_urls = {}
    for cat_key, items in categories.items():
        filename = "data.json" if cat_key == "all" else f"data-{cat_key}.json"
        _push_file(
            owner, repo, branch,
            f"demos/{slug}/{filename}",
            json.dumps(items, indent=2),
            f"demo: {slug} — {cat_key}",
        )
        endpoint_urls[cat_key] = f"https://{owner}.github.io/{repo}/demos/{slug}/{filename}"

    return endpoint_urls


def deploy_blueprint(blueprint: dict, slug: str) -> str:
    """Push the Playground blueprint JSON to GitHub Pages and return the public URL."""
    owner, repo = config.GITHUB_PAGES_REPO.split("/", 1)
    branch = config.GITHUB_PAGES_BRANCH

    _push_file(
        owner, repo, branch,
        f"demos/{slug}/blueprint.json",
        json.dumps(blueprint, indent=2),
        f"demo: add {slug} blueprint",
    )
    return f"https://{owner}.github.io/{repo}/demos/{slug}/blueprint.json"
