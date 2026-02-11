import base64
import os

import instaloader

import config


SESSION_DIR = os.path.expanduser("~/.config/instaloader")


def _get_session_path(username: str) -> str:
    return os.path.join(SESSION_DIR, f"session-{username}")


def is_logged_in() -> bool:
    """Check if there's an active Instagram session."""
    username = config.INSTAGRAM_USERNAME or ""
    if not username:
        return False

    session_path = _get_session_path(username)
    if os.path.exists(session_path):
        return True

    # Check if session is in env var
    if config.INSTAGRAM_SESSION_B64:
        return True

    return False


def get_session_username() -> str:
    """Return the username of the current session, or empty string."""
    return config.INSTAGRAM_USERNAME or ""


def _create_loader() -> instaloader.Instaloader:
    """Create a fresh Instaloader instance."""
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )


def login(username: str, password: str) -> dict:
    """Login to Instagram with username and password.

    Returns: {success: bool, needs_2fa: bool, error: str}
    """
    L = _create_loader()

    try:
        L.login(username, password)
        os.makedirs(SESSION_DIR, exist_ok=True)
        L.save_session_to_file(filename=_get_session_path(username))

        # Also save as base64 in env for persistence
        _save_session_to_env(username)

        # Update config in memory
        config.INSTAGRAM_USERNAME = username

        return {"success": True, "needs_2fa": False, "error": None}

    except instaloader.exceptions.TwoFactorAuthRequiredException:
        return {"success": False, "needs_2fa": True, "error": None}

    except instaloader.exceptions.BadCredentialsException:
        return {"success": False, "needs_2fa": False, "error": "Usuário ou senha incorretos."}

    except instaloader.exceptions.ConnectionException as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {
                "success": False, "needs_2fa": False,
                "error": "Instagram pediu verificação de segurança. Abra o Instagram no celular, "
                         "confirme que é você, e tente novamente."
            }
        return {"success": False, "needs_2fa": False, "error": f"Erro de conexão: {e}"}

    except Exception as e:
        return {"success": False, "needs_2fa": False, "error": f"Erro: {e}"}


def login_2fa(username: str, password: str, code: str) -> dict:
    """Complete login + 2FA in a single call (no need to store loader object).

    Re-creates the login flow and immediately provides the 2FA code.
    Returns: {success: bool, error: str}
    """
    L = _create_loader()

    try:
        L.login(username, password)
        # If login succeeds without 2FA this time, just save
        os.makedirs(SESSION_DIR, exist_ok=True)
        L.save_session_to_file(filename=_get_session_path(username))
        _save_session_to_env(username)
        config.INSTAGRAM_USERNAME = username
        return {"success": True, "error": None}

    except instaloader.exceptions.TwoFactorAuthRequiredException:
        try:
            L.two_factor_login(code)
            os.makedirs(SESSION_DIR, exist_ok=True)
            L.save_session_to_file(filename=_get_session_path(username))
            _save_session_to_env(username)
            config.INSTAGRAM_USERNAME = username
            return {"success": True, "error": None}

        except instaloader.exceptions.BadCredentialsException:
            return {"success": False, "error": "Código 2FA incorreto. Tente novamente."}

        except Exception as e:
            return {"success": False, "error": f"Erro no 2FA: {e}"}

    except instaloader.exceptions.BadCredentialsException:
        return {"success": False, "error": "Usuário ou senha incorretos."}

    except instaloader.exceptions.ConnectionException as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {
                "success": False,
                "error": "Instagram pediu verificação de segurança. Abra o app e confirme.",
            }
        return {"success": False, "error": f"Erro de conexão: {e}"}

    except Exception as e:
        return {"success": False, "error": f"Erro: {e}"}


def logout():
    """Remove the current session."""
    username = config.INSTAGRAM_USERNAME
    if username:
        session_path = _get_session_path(username)
        if os.path.exists(session_path):
            os.remove(session_path)

    config.INSTAGRAM_USERNAME = ""
    config.INSTAGRAM_SESSION_B64 = ""


def restore_session_from_env() -> bool:
    """Restore session file from INSTAGRAM_SESSION_B64 env var.

    Returns True if restored successfully.
    """
    if not config.INSTAGRAM_SESSION_B64 or not config.INSTAGRAM_USERNAME:
        return False

    try:
        session_bytes = base64.b64decode(config.INSTAGRAM_SESSION_B64)
        os.makedirs(SESSION_DIR, exist_ok=True)
        session_path = _get_session_path(config.INSTAGRAM_USERNAME)
        with open(session_path, "wb") as f:
            f.write(session_bytes)
        return True
    except Exception:
        return False


def _save_session_to_env(username: str):
    """Encode session file to base64 and store in config (memory only)."""
    session_path = _get_session_path(username)
    if os.path.exists(session_path):
        with open(session_path, "rb") as f:
            config.INSTAGRAM_SESSION_B64 = base64.b64encode(f.read()).decode()
