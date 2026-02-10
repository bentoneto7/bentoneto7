import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_radar.db")

# Scraping settings
DEFAULT_SCRAPE_LIMIT = 30
SCRAPE_DELAY_SECONDS = 3
