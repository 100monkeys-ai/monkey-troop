#!/bin/bash
set -e

echo "🐒 Monkey Troop - Quick Start"
echo "=============================="
echo ""

# Check for required tools
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting." >&2; exit 1; }

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    
    # Generate secret key
    if command -v openssl >/dev/null 2>&1; then
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i.bak "s/your_secret_key_here/$SECRET_KEY/" .env
        rm .env.bak 2>/dev/null || true
        echo "✓ Generated SECRET_KEY"
    else
        echo "⚠️  Please set SECRET_KEY in .env manually"
    fi
    
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and set:"
    echo "   - DB_PASSWORD (change from default)"
    echo "   - TS_AUTHKEY (get from Headscale)"
    echo ""
    read -p "Press Enter when ready to continue..."
fi

# Menu
echo ""
echo "What would you like to do?"
echo ""
echo "1) Start Coordinator (server)"
echo "2) Start Worker (donate GPU)"
echo "3) Build Rust binaries"
echo "4) Run tests"
echo "5) Exit"
echo ""
read -p "Choose [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting Coordinator..."
        docker-compose -f docker-compose.coordinator.yml up -d
        echo ""
        echo "✓ Coordinator started!"
        echo "  API: http://localhost:8000"
        echo "  Health: http://localhost:8000/health"
        echo ""
        echo "View logs: docker-compose -f docker-compose.coordinator.yml logs -f"
        ;;
    2)
        echo ""
        echo "🚀 Starting Worker..."
        if [ ! -f .env ]; then
            echo "❌ Please set TS_AUTHKEY in .env first"
            exit 1
        fi
        docker-compose -f docker-compose.worker.yml up -d
        echo ""
        echo "✓ Worker started!"
        echo ""
        echo "View logs: docker-compose -f docker-compose.worker.yml logs -f"
        ;;
    3)
        echo ""
        echo "🔨 Building Rust binaries..."
        cargo build --release
        echo ""
        echo "✓ Build complete!"
        echo "  Worker: ./target/release/monkey-troop-worker"
        echo "  Client: ./target/release/monkey-troop-client"
        ;;
    4)
        echo ""
        echo "🧪 Running tests..."
        cargo test --workspace
        cd coordinator && python -m pytest && cd ..
        echo ""
        echo "✓ Tests complete!"
        ;;
    5)
        echo "Goodbye! 🐒"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
