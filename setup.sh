#!/bin/bash

# OfficePlane Setup Script
# Initializes database, generates Prisma clients, and prepares the environment

set -e

echo "🚀 OfficePlane Setup"
echo "==================="
echo ""

# Check for required tools
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed. Aborting." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }

echo "✅ Prerequisites check passed"
echo ""

# Install root dependencies
echo "📦 Installing root dependencies..."
npm install
echo ""

# Install UI dependencies
echo "📦 Installing UI dependencies..."
cd ui && npm install && cd ..
echo ""

# Generate Prisma clients
echo "🔧 Generating Prisma clients..."
npx prisma generate
echo ""

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install -e ".[dev]"
echo ""

# Generate Python Prisma client
echo "🔧 Generating Python Prisma client..."
prisma generate
echo ""

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env <<EOF
# Database
DATABASE_URL="postgresql://officeplane:officeplane@localhost:5432/officeplane"

# OpenAI (for embeddings)
OPENAI_API_KEY=your_openai_api_key_here

# OfficePlane
OFFICEPLANE_DRIVER=libreoffice
POOL_SIZE=6

# Next.js
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
EOF
    echo "⚠️  Please edit .env and add your OPENAI_API_KEY"
    echo ""
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your OPENAI_API_KEY"
echo "  2. Start the services:"
echo "     $ docker compose up -d"
echo "  3. Run Prisma migrations:"
echo "     $ npx prisma migrate dev"
echo "  4. Access the UI:"
echo "     - Management Dashboard: http://localhost:3000"
echo "     - API Docs: http://localhost:8001/docs"
echo ""
