#!/bin/bash
clear
echo ""
echo " ╔══════════════════════════════════════╗"
echo " ║     Content Radar + Meta Ads         ║"
echo " ╚══════════════════════════════════════╝"
echo ""

# ── Verifica Python ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo " [ERRO] Python não encontrado."
    echo " Instale com: brew install python (Mac) ou sudo apt install python3 (Linux)"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

# ── Instala dependências ──────────────────────────────────────────────────────
echo " Instalando dependências..."
$PYTHON -m pip install -r requirements.txt -q

# ── Verifica .env ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo ""
    echo " [AVISO] Arquivo .env não encontrado. Criando modelo..."
    cat > .env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
META_APP_ID=1578109623477895
META_APP_SECRET=85135f6389f679cf1cc7ab44ca9b700f
META_ACCESS_TOKEN=EAANdZCniqb8wBRZA1Pb1xfvVu1DPTSA3B7YniV4gOCIXw1rHsmIyrJqw9CqiXBDVDmnZAxQMZAMESawydcjvZBLSla5LX8BZBaQrPwJoiFKGfLjrIYHLx4cN9RFsvS8ZAT5CApLFDsjZC8OGl4l7mqekrjYgn1GULcy2H3tMJMhUaeeWaGxxqjQBp12F9j4zGCjrChWWzA6GJZB8BKZA2O8UEmuSdLdlFCwZAiNXd3Khejl8GRt4ZACNUHDMmYVeQgujZCj5ZAwoIZCZCwNULUZB7kMe8t2bbrtGE
META_AD_ACCOUNT_ID=act_2184917148607388
INSTAGRAM_USERNAME=seu_usuario
INSTAGRAM_PASSWORD=sua_senha
EOF
    echo " Arquivo .env criado. Preencha as credenciais e rode novamente."
    open .env 2>/dev/null || xdg-open .env 2>/dev/null || nano .env
    exit 0
fi

# ── Inicia o app ──────────────────────────────────────────────────────────────
echo ""
echo " Iniciando Content Radar..."
echo " Acesse: http://localhost:8501"
echo ""
open http://localhost:8501 2>/dev/null || xdg-open http://localhost:8501 2>/dev/null &
$PYTHON -m streamlit run app.py --server.port=8501 --server.address=localhost
