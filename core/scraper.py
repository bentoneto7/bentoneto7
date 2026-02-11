import base64
import os
import tempfile
import time
from itertools import islice
from datetime import datetime

import instaloader

import config
from core import database


def _restore_session_from_env():
    """Restore instaloader session file from INSTAGRAM_SESSION_B64 env var."""
    if not config.INSTAGRAM_SESSION_B64 or not config.INSTAGRAM_USERNAME:
        return None

    try:
        session_bytes = base64.b64decode(config.INSTAGRAM_SESSION_B64)
        session_dir = os.path.expanduser("~/.config/instaloader")
        os.makedirs(session_dir, exist_ok=True)
        session_path = os.path.join(session_dir, f"session-{config.INSTAGRAM_USERNAME}")
        with open(session_path, "wb") as f:
            f.write(session_bytes)
        return session_path
    except Exception:
        return None


def _get_loader() -> instaloader.Instaloader:
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    # Configure proxy if set (needed for cloud/datacenter IPs)
    if config.PROXY_URL:
        L.context._session.proxies = {
            "http": config.PROXY_URL,
            "https": config.PROXY_URL,
        }

    # Try to load session: first from env var (cloud), then from file (local)
    if config.INSTAGRAM_USERNAME:
        _restore_session_from_env()
        try:
            L.load_session_from_file(config.INSTAGRAM_USERNAME)
        except FileNotFoundError:
            if config.INSTAGRAM_PASSWORD:
                L.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)

    return L


def _map_post_type(typename: str) -> str:
    mapping = {
        "GraphImage": "image",
        "GraphVideo": "video",
        "GraphSidecar": "carousel",
    }
    return mapping.get(typename, "image")


def scrape_account(username: str, max_posts: int = None) -> dict:
    """Scrape recent posts from an Instagram account.

    Returns a dict with status info: {success, posts_scraped, error}
    """
    if max_posts is None:
        max_posts = config.DEFAULT_SCRAPE_LIMIT

    L = _get_loader()

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        return {"success": False, "posts_scraped": 0, "error": f"Perfil @{username} não existe"}
    except instaloader.exceptions.ConnectionException as e:
        error_str = str(e).lower()
        if "429" in error_str or "too many" in error_str:
            msg = (
                "Instagram bloqueou temporariamente (rate limit). "
                "Isso é comum em servidores cloud. "
                "Configure INSTAGRAM_SESSION_B64 nas variáveis de ambiente "
                "(veja instruções na página Contas)."
            )
        elif "redirect" in error_str or "login" in error_str:
            msg = (
                "Instagram redirecionou para login — o IP do servidor está bloqueado. "
                "Configure INSTAGRAM_SESSION_B64 nas variáveis de ambiente "
                "(veja instruções na página Contas)."
            )
        else:
            msg = (
                f"Erro de conexão com Instagram: {e}. "
                "Configure INSTAGRAM_SESSION_B64 nas variáveis de ambiente "
                "(veja instruções na página Contas)."
            )
        return {"success": False, "posts_scraped": 0, "error": msg}
    except Exception as e:
        return {"success": False, "posts_scraped": 0, "error": f"Erro inesperado: {e}"}

    if profile.is_private and not profile.followed_by_viewer:
        database.update_account_info(
            username=username,
            full_name=profile.full_name,
            followers=profile.followers,
            following=profile.followees,
            bio=profile.biography,
            is_private=True,
        )
        return {"success": False, "posts_scraped": 0, "error": f"Perfil @{username} é privado"}

    # Update account info
    database.update_account_info(
        username=username,
        full_name=profile.full_name,
        followers=profile.followers,
        following=profile.followees,
        bio=profile.biography,
        is_private=profile.is_private,
    )

    posts_scraped = 0
    for post in islice(profile.get_posts(), max_posts):
        try:
            followers = profile.followers if profile.followers > 0 else 1
            engagement_rate = (post.likes + post.comments) / followers

            post_data = {
                "shortcode": post.shortcode,
                "account_username": username,
                "caption": post.caption or "",
                "hashtags": list(post.caption_hashtags),
                "post_type": _map_post_type(post.typename),
                "likes": post.likes,
                "comments": post.comments,
                "engagement_rate": round(engagement_rate, 6),
                "posted_at": post.date_utc.isoformat(),
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
            }

            database.upsert_post(post_data)
            posts_scraped += 1
        except instaloader.exceptions.ConnectionException:
            # Rate limited mid-scrape, return what we got so far
            break
        except Exception:
            continue

    return {"success": True, "posts_scraped": posts_scraped, "error": None}


def scrape_all_accounts() -> list[dict]:
    """Scrape all monitored accounts. Returns list of results per account."""
    accounts = database.get_accounts()
    results = []

    for account in accounts:
        result = scrape_account(account["username"])
        result["username"] = account["username"]
        results.append(result)
        time.sleep(config.SCRAPE_DELAY_SECONDS)

    return results
