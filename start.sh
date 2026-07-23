#!/bin/bash
# ─────────────────────────────────────────────
#  ENCARNADO — Arranque do servidor
# ─────────────────────────────────────────────

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ENCARNADO — Portal do Benfica      ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 não encontrado. Instale em https://python.org"
    exit 1
fi

# Instalar dependências
echo "  → A instalar dependências..."
pip3 install -r requirements.txt -q

# Criar pastas necessárias (os dados ficam na Rocketadmin, não em ficheiro local)
mkdir -p public/assets/images

# Arrancar servidor
echo "  → A iniciar servidor..."
echo ""
echo "  Site público : http://localhost:5000"
echo "  Administração: http://localhost:5000/admin"
echo "  Login        : admin / encarnado2025"
echo ""
echo "  Pressione CTRL+C para parar."
echo ""

python3 server.py
