#!/usr/bin/env bash
set -e

echo "================================================"
echo " ci-wiki — Competitive Intelligence Wiki Setup  "
echo "================================================"
echo ""

# Install package and all dependencies
echo "▶ Installing dependencies..."
pip install -e ".[dev]" -q
echo "  ✓ Dependencies installed"

# Ensure required directories exist
mkdir -p data sources wiki/companies wiki/products wiki/people wiki/trends
echo "  ✓ Directories ready"

# Run test suite to verify everything works
echo ""
echo "▶ Running test suite..."
python -m pytest tests/ -q --tb=short
echo ""

# Check for API key
echo "================================================"
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  ✓ ANTHROPIC_API_KEY is set — you're ready to go!"
else
    echo "  ⚠ ANTHROPIC_API_KEY is not set."
    echo ""
    echo "  To fix this, add it as a Codespaces secret:"
    echo "    github.com → Settings → Codespaces → Secrets"
    echo "    Add secret: ANTHROPIC_API_KEY = sk-ant-..."
    echo ""
    echo "  Or set it in your terminal for this session:"
    echo "    export ANTHROPIC_API_KEY=sk-ant-..."
fi
echo "================================================"
echo ""
echo "Quick start:"
echo "  make ingest-demo     # ingest 3 AI company pages"
echo "  make query-demo      # ask a sample question"
echo "  make help            # see all available commands"
echo ""
