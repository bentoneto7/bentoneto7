"""Creative radar-themed loaders for all waiting actions."""
import random
import streamlit as st

# ─── Themed messages per context ───

_MESSAGES = {
    "login": [
        "Sintonizando frequência do Instagram...",
        "Abrindo o cofre de sessão...",
        "Estabelecendo conexão com o satélite...",
        "Girando a chave na fechadura digital...",
        "Calibrando sinal de autenticação...",
    ],
    "2fa": [
        "Decifrando o código secreto...",
        "Validando camada extra de segurança...",
        "Encaixando a última peça do quebra-cabeça...",
        "Destravando a segunda fechadura...",
        "Conferindo impressão digital...",
    ],
    "scrape_self": [
        "Escaneando seu território digital...",
        "Radar varrendo seu perfil...",
        "Mapeando seu universo de conteúdo...",
        "Interceptando dados do seu feed...",
        "Mirando nos seus melhores posts...",
    ],
    "ai_analysis": [
        "Neurônios artificiais analisando padrões...",
        "IA examinando seu DNA de conteúdo...",
        "Processando insights com inteligência artificial...",
        "Identificando a paleta do seu nicho...",
        "Calculando a geometria do seu estilo...",
    ],
    "scrape_account": [
        "Radar captando sinais de @{username}...",
        "Telescópio focando em @{username}...",
        "Satélite sobrevoando @{username}...",
        "Decodificando transmissões de @{username}...",
        "Interceptando dados de @{username}...",
        "Captando frequência de @{username}...",
        "Zoom no perfil de @{username}...",
        "Catalogando posts de @{username}...",
    ],
    "scrape_done": [
        "Sinal captado com sucesso!",
        "Transmissão recebida!",
        "Dados decodificados!",
        "Frequência estabilizada!",
    ],
}


def get_message(context: str, **kwargs) -> str:
    """Get a random creative message for the given context."""
    msgs = _MESSAGES.get(context, ["Processando..."])
    msg = random.choice(msgs)
    return msg.format(**kwargs) if kwargs else msg


def get_message_by_index(context: str, index: int, **kwargs) -> str:
    """Get a creative message by index (cycles through the list)."""
    msgs = _MESSAGES.get(context, ["Processando..."])
    msg = msgs[index % len(msgs)]
    return msg.format(**kwargs) if kwargs else msg


# ─── CSS Animated Radar Loader ───

_RADAR_CSS = """
<style>
@keyframes cr-sweep {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
@keyframes cr-ping {
    0%   { transform: scale(0.6); opacity: 0.8; }
    70%  { transform: scale(1.8); opacity: 0; }
    100% { transform: scale(0.6); opacity: 0; }
}
@keyframes cr-dot-pulse {
    0%, 80%, 100% { opacity: 0; transform: scale(0.6); }
    40% { opacity: 1; transform: scale(1); }
}
@keyframes cr-text-fade {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
.cr-loader-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 1.5rem 0;
    gap: 0.8rem;
}
.cr-radar {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    position: relative;
    background: radial-gradient(circle, rgba(34,197,94,0.08) 0%, transparent 70%);
    border: 2px solid rgba(34,197,94,0.25);
}
.cr-radar::before {
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    width: 50%; height: 2px;
    background: linear-gradient(90deg, rgba(34,197,94,0.9), transparent);
    transform-origin: left center;
    animation: cr-sweep 1.8s linear infinite;
}
.cr-radar::after {
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    width: 45px; height: 45px;
    border-radius: 50%;
    border: 1.5px solid rgba(34,197,94,0.3);
    transform: translate(-50%, -50%);
    animation: cr-ping 1.8s ease-out infinite;
}
.cr-center-icon {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    font-size: 1.3rem;
    z-index: 2;
}
.cr-dots {
    display: flex;
    gap: 6px;
    margin-top: 2px;
}
.cr-dots span {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: rgba(34,197,94,0.7);
    animation: cr-dot-pulse 1.4s ease-in-out infinite;
}
.cr-dots span:nth-child(2) { animation-delay: 0.2s; }
.cr-dots span:nth-child(3) { animation-delay: 0.4s; }
.cr-msg {
    color: #999;
    font-size: 0.9rem;
    text-align: center;
    animation: cr-text-fade 2s ease-in-out infinite;
    max-width: 350px;
}
.cr-sub {
    color: #666;
    font-size: 0.75rem;
    text-align: center;
}
</style>
"""

_ICONS = {
    "login": "🔐",
    "2fa": "🛡️",
    "scrape_self": "📡",
    "scrape_account": "🛰️",
    "ai_analysis": "🧠",
    "scrape_bulk": "📡",
}


def radar_loader(context: str, subtitle: str = "", **kwargs) -> None:
    """Display a radar-themed animated loader with a creative message.

    Usage:
        placeholder = st.empty()
        with placeholder.container():
            radar_loader("scrape_account", username="natgeo")
        # ... do work ...
        placeholder.empty()
    """
    msg = get_message(context, **kwargs)
    icon = _ICONS.get(context, "📡")

    st.markdown(_RADAR_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="cr-loader-wrap">
            <div class="cr-radar">
                <div class="cr-center-icon">{icon}</div>
            </div>
            <div class="cr-dots">
                <span></span><span></span><span></span>
            </div>
            <div class="cr-msg">{msg}</div>
            {f'<div class="cr-sub">{subtitle}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def progress_loader(context: str, current: int, total: int, **kwargs) -> str:
    """Return a creative progress message for multi-step operations."""
    msg = get_message_by_index(context, current, **kwargs)
    return f"{msg} ({current + 1}/{total})"
