#!/bin/bash

# Speaking Coach - Quick Start Script
# Run this after cloning to set up local development

set -e

echo "🎤 Speaking Coach - Quick Start"
echo "================================"
echo ""

# Check dependencies
echo "✓ Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install from https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ Git not found. Install from https://git-scm.com"
    exit 1
fi

echo "✓ Docker and Git found"
echo ""

# Create .env from template
echo "✓ Setting up environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ Created .env file"
    echo "  ⚠️  Edit .env and add your API keys!"
    echo "     See API_KEYS.md for instructions"
else
    echo "✓ .env already exists"
fi

echo ""
echo "✓ Starting Docker services..."
docker-compose up -d

echo "  ⏳ Waiting for services to be ready..."
sleep 10

echo "✓ Services running!"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - Backend API: http://localhost:8000"
echo ""

# Initialize database
echo "✓ Initializing database..."
docker-compose exec -T backend python -c "from backend.src.db.database import init_db; init_db()" || true

echo ""
echo "✓ Backend setup complete!"
echo ""

# Setup web frontend
echo "✓ Setting up web frontend..."
cd web
if [ ! -d node_modules ]; then
    npm install
fi
echo "✓ Web dependencies installed"
cd ..

echo ""
echo "================================"
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:8000 in your browser to test the backend"
echo "2. In another terminal, run: cd web && npm run dev"
echo "3. Open http://localhost:3000 to access the web app"
echo "4. Create an account and start coaching!"
echo ""
echo "For API keys, see API_KEYS.md"
echo "For help, see SETUP.md"
echo ""
