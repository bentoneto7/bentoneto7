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


def _checkpoint_message() -> str:
    return (
        "O Instagram bloqueou o login por segurança (Checkpoint).\n\n"
        "Isso acontece porque o servidor usa um IP de datacenter.\n\n"
        "**Como resolver:**\n"
        "1. Abra o Instagram no celular\n"
        "2. Confirme o alerta de 'atividade suspeita' (se aparecer)\n"
        "3. Volte aqui e tente logar novamente\n\n"
        "Se continuar falhando, configure um **PROXY_URL** residencial "
        "nas variáveis de ambiente do Railway."
    )


def _classify_connection_error(e: Exception) -> str:
    error_str = str(e).lower()
    if "checkpoint" in error_str or "challenge" in error_str:
        return _checkpoint_message()
    if "429" in error_str or "too many" in error_str:
        return "Instagram bloqueou temporariamente (rate limit). Aguarde alguns minutos."
    return f"Erro de conexão: {e}"


def login(username: str, password: str, remember: bool = False) -> dict:
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

        # Persist session to database
        _persist_session_to_db(username, remember)

        # Update config in memory
        config.INSTAGRAM_USERNAME = username

        return {"success": True, "needs_2fa": False, "error": None}

    except instaloader.exceptions.TwoFactorAuthRequiredException:
        return {"success": False, "needs_2fa": True, "error": None}

    except instaloader.exceptions.BadCredentialsException:
        return {"success": False, "needs_2fa": False, "error": "Usuário ou senha incorretos."}

    except instaloader.exceptions.ConnectionException as e:
        return {"success": False, "needs_2fa": False, "error": _classify_connection_error(e)}

    except Exception as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {"success": False, "needs_2fa": False, "error": _checkpoint_message()}
        return {"success": False, "needs_2fa": False, "error": f"Erro: {e}"}


def login_2fa(username: str, password: str, code: str, remember: bool = False) -> dict:
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
        _persist_session_to_db(username, remember)
        config.INSTAGRAM_USERNAME = username
        return {"success": True, "error": None}

    except instaloader.exceptions.TwoFactorAuthRequiredException:
        try:
            L.two_factor_login(code)
            os.makedirs(SESSION_DIR, exist_ok=True)
            L.save_session_to_file(filename=_get_session_path(username))
            _save_session_to_env(username)
            _persist_session_to_db(username, remember)
            config.INSTAGRAM_USERNAME = username
            return {"success": True, "error": None}

        except instaloader.exceptions.BadCredentialsException:
            return {"success": False, "error": "Código 2FA incorreto. Tente novamente."}

        except Exception as e:
            return {"success": False, "error": f"Erro no 2FA: {e}"}

    except instaloader.exceptions.BadCredentialsException:
        return {"success": False, "error": "Usuário ou senha incorretos."}

    except instaloader.exceptions.ConnectionException as e:
        return {"success": False, "error": _classify_connection_error(e)}

    except Exception as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {"success": False, "error": _checkpoint_message()}
        return {"success": False, "error": f"Erro: {e}"}


def logout():
    """Remove the current session (file, memory, and database)."""
    from core import database

    username = config.INSTAGRAM_USERNAME
    if username:
        session_path = _get_session_path(username)
        if os.path.exists(session_path):
            os.remove(session_path)
        database.clear_user_session(username)

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


def restore_session_from_db() -> bool:
    """Try to restore a saved session from the database.

    This is the primary "remember login" mechanism.
    Returns True if a valid session was restored.
    """
    from core import database

    database.cleanup_expired_sessions()

    saved = database.get_saved_session()
    if not saved:
        return False

    username = saved["username"]
    session_b64 = saved["session_b64"]

    try:
        session_bytes = base64.b64decode(session_b64)
        os.makedirs(SESSION_DIR, exist_ok=True)
        session_path = _get_session_path(username)
        with open(session_path, "wb") as f:
            f.write(session_bytes)

        config.INSTAGRAM_USERNAME = username
        config.INSTAGRAM_SESSION_B64 = session_b64
        return True
    except Exception:
        database.clear_user_session(username)
        return False


def _persist_session_to_db(username: str, remember: bool = False):
    """Save the current session to the database for persistence."""
    from core import database

    session_path = _get_session_path(username)
    if os.path.exists(session_path):
        with open(session_path, "rb") as f:
            session_b64 = base64.b64encode(f.read()).decode()
        database.save_user_session(username, session_b64, remember=remember)


def _save_session_to_env(username: str):
    """Encode session file to base64 and store in config (memory only)."""
    session_path = _get_session_path(username)
    if os.path.exists(session_path):
        with open(session_path, "rb") as f:
            config.INSTAGRAM_SESSION_B64 = base64.b64encode(f.read()).decode()
