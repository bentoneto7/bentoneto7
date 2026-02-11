import logging
import time
from itertools import islice
from datetime import datetime

import instaloader
from requests.adapters import HTTPAdapter

import config
from core import database, auth

log = logging.getLogger(__name__)


class _TimeoutAdapter(HTTPAdapter):
    """HTTP adapter that enforces a default timeout on all requests."""
    def __init__(self, timeout=30, **kwargs):
        self.timeout = timeout
        super().__init__(**kwargs)

    def send(self, *args, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return super().send(*args, **kwargs)


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

    # Configure proxy FIRST (before mounting adapters)
    if config.PROXY_URL:
        L.context._session.proxies = {
            "http": config.PROXY_URL,
            "https": config.PROXY_URL,
        }
        log.info("Scraper proxy configurado: %s", config.PROXY_URL[:30] + "...")

    # Enforce 30s timeout on all HTTP requests to prevent infinite hangs
    adapter = _TimeoutAdapter(timeout=30)
    L.context._session.mount("http://", adapter)
    L.context._session.mount("https://", adapter)

    # Load session from file (created by auth.login or auth.restore_session_from_env)
    if config.INSTAGRAM_USERNAME:
        try:
            L.load_session_from_file(config.INSTAGRAM_USERNAME)
            log.info("Session loaded for @%s", config.INSTAGRAM_USERNAME)
        except FileNotFoundError:
            log.warning("Session file not found for @%s", config.INSTAGRAM_USERNAME)

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

    if not auth.is_logged_in():
        log.warning("scrape_account(@%s): not logged in", username)
        return {
            "success": False, "posts_scraped": 0,
            "error": "Faça login no Instagram primeiro (página principal)."
        }

    log.info("scrape_account(@%s): starting (max_posts=%d)", username, max_posts)
    L = _get_loader()

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        log.warning("scrape_account(@%s): profile not found", username)
        return {"success": False, "posts_scraped": 0, "error": f"Perfil @{username} não existe"}
    except instaloader.exceptions.ConnectionException as e:
        error_str = str(e).lower()
        log.error("scrape_account(@%s): ConnectionException: %s", username, e)
        if "429" in error_str or "too many" in error_str:
            msg = (
                "Instagram bloqueou temporariamente (rate limit). "
                "Aguarde alguns minutos e tente novamente."
            )
        elif "redirect" in error_str or "login" in error_str:
            msg = (
                "Sessão expirada — o Instagram pediu login novamente. "
                "Volte à página principal e faça login novamente."
            )
        else:
            msg = f"Erro de conexão com Instagram: {e}"
        return {"success": False, "posts_scraped": 0, "error": msg}
    except (TimeoutError, OSError) as e:
        return {"success": False, "posts_scraped": 0, "error": "Timeout ao conectar ao Instagram. Tente novamente."}
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
    errors = []
    timeout_seconds = 45  # Max 45 seconds per account
    start_time = time.time()

    for post in islice(profile.get_posts(), max_posts):
        # Check total timeout
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            errors.append(f"Timeout: coleta parou após {int(elapsed)}s ({posts_scraped} posts coletados)")
            break

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
        except instaloader.exceptions.ConnectionException as e:
            error_str = str(e).lower()
            if "429" in error_str or "too many" in error_str:
                errors.append("Rate limit atingido pelo Instagram.")
            elif "redirect" in error_str or "login" in error_str:
                errors.append("Sessão expirada. Faça login novamente.")
            else:
                errors.append(f"Erro de conexão: {e}")
            break
        except (TimeoutError, OSError):
            errors.append("Timeout na requisição. Coleta parcial.")
            break
        except Exception as e:
            errors.append(f"Erro no post: {e}")
            continue

    if posts_scraped > 0:
        error_msg = "; ".join(errors) if errors else None
        log.info("scrape_account(@%s): OK — %d posts scraped", username, posts_scraped)
        return {"success": True, "posts_scraped": posts_scraped, "error": error_msg}
    elif errors:
        log.warning("scrape_account(@%s): FAILED — %s", username, "; ".join(errors))
        return {"success": False, "posts_scraped": 0, "error": "; ".join(errors)}
    else:
        log.info("scrape_account(@%s): no posts found", username)
        return {"success": True, "posts_scraped": 0, "error": "Nenhum post encontrado."}


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


def get_similar_profiles(username: str, limit: int = 5) -> list[dict]:
    """Get similar profiles based on a user's followees.

    Analyzes the accounts followed by the given user and returns
    public profiles with the most followers (likely influencers/creators).

    Returns list of dicts: {username, full_name, followers, bio, is_private}
    """
    if not auth.is_logged_in():
        return []

    L = _get_loader()

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except Exception:
        return []

    suggestions = []
    seen = set()
    checked = 0

    try:
        for followee in profile.get_followees():
            if checked >= 50:  # Check up to 50 followees to find good suggestions
                break
            checked += 1

            if followee.username in seen:
                continue
            seen.add(followee.username)

            # Skip private accounts and very small accounts
            if followee.is_private:
                continue
            if followee.followers < 10000:
                continue

            suggestions.append({
                "username": followee.username,
                "full_name": followee.full_name or "",
                "followers": followee.followers,
                "bio": (followee.biography or "")[:150],
                "is_private": followee.is_private,
            })

            time.sleep(0.3)  # Small delay to avoid rate limits

    except instaloader.exceptions.ConnectionException:
        pass  # Return what we have so far
    except Exception:
        pass

    # Sort by followers (most popular first) and return top N
    suggestions.sort(key=lambda x: x["followers"], reverse=True)
    return suggestions[:limit]


def get_profile_info(username: str) -> dict:
    """Get basic profile info without scraping posts.

    Returns: {success, username, full_name, followers, following, bio, is_private}
    """
    if not auth.is_logged_in():
        return {"success": False, "error": "Não autenticado"}

    L = _get_loader()

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "success": True,
            "username": profile.username,
            "full_name": profile.full_name,
            "followers": profile.followers,
            "following": profile.followees,
            "bio": profile.biography or "",
            "is_private": profile.is_private,
        }
    except instaloader.exceptions.ProfileNotExistsException:
        return {"success": False, "error": f"Perfil @{username} não existe"}
    except Exception as e:
        return {"success": False, "error": str(e)}
