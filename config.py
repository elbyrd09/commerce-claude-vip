import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_PAGES_REPO = os.environ.get("GITHUB_PAGES_REPO", "")  # "owner/repo"
GITHUB_PAGES_BRANCH = os.environ.get("GITHUB_PAGES_BRANCH", "gh-pages")
