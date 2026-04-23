@echo off
chcp 65001 >nul
title Content Radar — iniciando...

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     Content Radar + Meta Ads         ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Verifica Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado.
    echo  Baixe em: https://python.org/downloads
    echo  Marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

REM ── Instala dependencias ─────────────────────────────────────────────────────
echo  Instalando dependencias...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo  [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

REM ── Verifica .env ────────────────────────────────────────────────────────────
if not exist ".env" (
    echo.
    echo  [AVISO] Arquivo .env nao encontrado.
    echo  Criando modelo...
    (
        echo ANTHROPIC_API_KEY=sk-ant-...
        echo META_APP_ID=1578109623477895
        echo META_APP_SECRET=85135f6389f679cf1cc7ab44ca9b700f
        echo META_ACCESS_TOKEN=cole_seu_token_aqui
        echo META_AD_ACCOUNT_ID=act_2184917148607388
        echo INSTAGRAM_USERNAME=seu_usuario
        echo INSTAGRAM_PASSWORD=sua_senha
    ) > .env
    echo  Arquivo .env criado. Abra-o e preencha suas credenciais, depois rode novamente.
    start notepad .env
    pause
    exit /b 0
)

REM ── Inicia o app ─────────────────────────────────────────────────────────────
echo.
echo  Iniciando Content Radar...
echo  Acesse: http://localhost:8501
echo.
start http://localhost:8501
streamlit run app.py --server.port=8501 --server.address=localhost --server.headless=false

pause
