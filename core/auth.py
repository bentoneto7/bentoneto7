import base64
import logging
import os

import requests
import instaloader

import config

log = logging.getLogger(__name__)

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


def verify_session() -> dict:
    """Test if the current session is actually valid with Instagram.

    Returns: {valid: bool, username: str, error: str}
    """
    if not is_logged_in():
        return {"valid": False, "username": "", "error": "Nenhuma sessão encontrada"}

    username = config.INSTAGRAM_USERNAME
    L = _create_loader()

    try:
        L.load_session_from_file(username)
        # Test with a simple profile lookup (the user's own profile)
        profile = instaloader.Profile.from_username(L.context, username)
        log.info("Session valid for @%s (followers: %d)", username, profile.followers)
        return {"valid": True, "username": username, "error": None}
    except FileNotFoundError:
        log.warning("Session file missing for @%s", username)
        return {"valid": False, "username": username, "error": "Arquivo de sessão não encontrado"}
    except instaloader.exceptions.ConnectionException as e:
        error_str = str(e).lower()
        if "redirect" in error_str or "login" in error_str:
            log.warning("Session expired for @%s", username)
            return {"valid": False, "username": username, "error": "Sessão expirada — faça login novamente"}
        if "checkpoint" in error_str or "challenge" in error_str:
            return {"valid": False, "username": username, "error": "Instagram pediu verificação de segurança"}
        if "429" in error_str:
            # Rate limited but session might still be valid
            return {"valid": True, "username": username, "error": "Rate limit (sessão pode estar OK)"}
        return {"valid": False, "username": username, "error": f"Erro de conexão: {e}"}
    except Exception as e:
        log.warning("Session verification failed for @%s: %s", username, e)
        return {"valid": False, "username": username, "error": str(e)}


def test_proxy() -> dict:
    """Test if the configured proxy is working. Returns {ok, ip, error}."""
    if not config.PROXY_URL:
        return {"ok": False, "ip": None, "error": "PROXY_URL não configurada"}

    proxies = {"http": config.PROXY_URL, "https": config.PROXY_URL}
    try:
        resp = requests.get(
            "https://ipv4.icanhazip.com",
            proxies=proxies,
            timeout=15,
        )
        ip = resp.text.strip()
        log.info("Proxy test OK — IP: %s", ip)
        return {"ok": True, "ip": ip, "error": None}
    except Exception as e:
        log.warning("Proxy test FAILED: %s", e)
        return {"ok": False, "ip": None, "error": str(e)}


def _create_loader() -> instaloader.Instaloader:
    """Create a fresh Instaloader instance with proxy + timeout support."""
    from requests.adapters import HTTPAdapter

    class _TimeoutAdapter(HTTPAdapter):
        def __init__(self, timeout=30, **kwargs):
            self.timeout = timeout
            super().__init__(**kwargs)

        def send(self, *args, **kwargs):
            kwargs.setdefault("timeout", self.timeout)
            return super().send(*args, **kwargs)

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    # Proxy support (critical for login from cloud/datacenter IPs)
    # Set proxies BEFORE mounting adapters so adapter inherits proxy config
    if config.PROXY_URL:
        L.context._session.proxies = {
            "http": config.PROXY_URL,
            "https": config.PROXY_URL,
        }
        log.info("Proxy configurado: %s", config.PROXY_URL[:30] + "...")

    # Timeout to prevent infinite hangs
    adapter = _TimeoutAdapter(timeout=30)
    L.context._session.mount("http://", adapter)
    L.context._session.mount("https://", adapter)

    return L


def _checkpoint_message(proxy_info: dict | None = None) -> str:
    msg = "O Instagram bloqueou o login por segurança (Checkpoint).\n\n"

    if proxy_info and proxy_info.get("ok"):
        msg += (
            f"**Proxy ativo** — IP usado: `{proxy_info['ip']}`\n\n"
            "O proxy está funcionando, mas o Instagram ainda bloqueou. "
            "Possíveis causas:\n"
            "- O IP do proxy já foi marcado pelo Instagram\n"
            "- A conta tem proteção extra ativada\n\n"
            "**Tente:**\n"
            "1. Abra o Instagram no celular e confirme o alerta de segurança\n"
            "2. Aguarde 5-10 minutos e tente novamente\n"
            "3. No IPRoyal, gere uma nova sessão (mude o session ID)\n"
        )
    elif proxy_info and not proxy_info.get("ok"):
        msg += (
            f"**Proxy NÃO está funcionando!** Erro: {proxy_info.get('error', 'desconhecido')}\n\n"
            "O login foi feito sem proxy (IP do datacenter), por isso foi bloqueado.\n\n"
            "**Verifique:**\n"
            "1. A variável `PROXY_URL` no Railway está correta?\n"
            "2. Formato esperado: `http://user:pass@host:port`\n"
            "3. O proxy está ativo no painel do IPRoyal?\n"
        )
    else:
        msg += (
            "**PROXY_URL não configurada.** O login foi feito com o IP do Railway (datacenter).\n\n"
            "**Configure um proxy residencial:**\n"
            "1. Adicione `PROXY_URL` nas variáveis de ambiente do Railway\n"
            "2. Formato: `http://user:pass@host:port`\n"
        )

    return msg


def _classify_connection_error(e: Exception, proxy_info: dict | None = None) -> str:
    error_str = str(e).lower()
    if "checkpoint" in error_str or "challenge" in error_str:
        return _checkpoint_message(proxy_info)
    if "429" in error_str or "too many" in error_str:
        return "Instagram bloqueou temporariamente (rate limit). Aguarde alguns minutos."
    if proxy_info and not proxy_info.get("ok"):
        return f"Erro de conexão (proxy com problema): {e}"
    return f"Erro de conexão: {e}"


def login(username: str, password: str, remember: bool = False) -> dict:
    """Login to Instagram with username and password.

    Returns: {success: bool, needs_2fa: bool, error: str}
    """
    # Test proxy before attempting login
    proxy_info = test_proxy() if config.PROXY_URL else None
    log.info("Login attempt — proxy_info: %s", proxy_info)

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
        return {"success": False, "needs_2fa": False, "error": _classify_connection_error(e, proxy_info)}

    except Exception as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {"success": False, "needs_2fa": False, "error": _checkpoint_message(proxy_info)}
        return {"success": False, "needs_2fa": False, "error": f"Erro: {e}"}


def login_2fa(username: str, password: str, code: str, remember: bool = False) -> dict:
    """Complete login + 2FA in a single call (no need to store loader object).

    Re-creates the login flow and immediately provides the 2FA code.
    Returns: {success: bool, error: str}
    """
    proxy_info = test_proxy() if config.PROXY_URL else None
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
        return {"success": False, "error": _classify_connection_error(e, proxy_info)}

    except Exception as e:
        error_str = str(e).lower()
        if "checkpoint" in error_str or "challenge" in error_str:
            return {"success": False, "error": _checkpoint_message(proxy_info)}
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


def auto_login_from_env() -> bool:
    """Auto-login using INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD env vars.

    Used on first deploy when no saved session exists yet.
    Returns True if login succeeded.
    """
    username = config.INSTAGRAM_USERNAME
    password = config.INSTAGRAM_PASSWORD
    if not username or not password:
        return False

    log.info("Attempting auto-login from env vars for @%s", username)
    result = login(username, password, remember=True)

    if result["success"]:
        log.info("Auto-login successful for @%s", username)
        return True

    if result.get("needs_2fa"):
        log.warning("Auto-login for @%s requires 2FA — manual login needed", username)
    else:
        log.warning("Auto-login failed for @%s: %s", username, result.get("error", ""))

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
