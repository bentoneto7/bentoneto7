import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Instagram credentials (recommended for cloud deploys to avoid rate limits)
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# Proxy for cloud environments where Instagram blocks datacenter IPs
# Format: "http://user:pass@host:port"
PROXY_URL = os.getenv("PROXY_URL", "")

# Instagram session cookie (base64-encoded session file for cloud deploys)
# Generated locally with: instaloader --login YOUR_USER
# Then encode: base64 ~/.config/instaloader/session-YOUR_USER
INSTAGRAM_SESSION_B64 = os.getenv("INSTAGRAM_SESSION_B64", "")

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_radar.db")

# Scraping settings
DEFAULT_SCRAPE_LIMIT = 30
SCRAPE_DELAY_SECONDS = 3

# Meta Ads (Facebook Marketing API)
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "")
