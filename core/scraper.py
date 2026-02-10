import time
from itertools import islice
from datetime import datetime

import instaloader

import config
from core import database


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

    if config.INSTAGRAM_USERNAME:
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
        return {"success": False, "posts_scraped": 0, "error": f"Erro de conexão: {e}"}

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
        except Exception as e:
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
