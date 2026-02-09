#!/bin/bash
# Monkey Troop Development Shortcuts

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐒 Monkey Troop Dev Tools${NC}"
echo ""

case "$1" in
    "build")
        echo -e "${GREEN}Building Rust workspace...${NC}"
        cargo build --release
        ;;
    
    "check")
        echo -e "${GREEN}Checking code...${NC}"
        cargo check --workspace
        cargo clippy --all-targets
        cd coordinator && black --check . && ruff check .
        ;;
    
    "fmt")
        echo -e "${GREEN}Formatting code...${NC}"
        cargo fmt --all
        cd coordinator && black .
        ;;
    
    "test")
        echo -e "${GREEN}Running tests...${NC}"
        cargo test --workspace
        cd coordinator && pytest
        ;;
    
    "coord")
        echo -e "${GREEN}Starting coordinator...${NC}"
        docker-compose -f docker-compose.coordinator.yml up
        ;;
    
    "coord-logs")
        echo -e "${GREEN}Showing coordinator logs...${NC}"
        docker-compose -f docker-compose.coordinator.yml logs -f
        ;;
    
    "worker")
        echo -e "${GREEN}Starting worker...${NC}"
        cargo run --bin monkey-troop-worker
        ;;
    
    "client")
        echo -e "${GREEN}Starting client...${NC}"
        cargo run --bin monkey-troop-client up
        ;;
    
    "clean")
        echo -e "${RED}Cleaning build artifacts...${NC}"
        cargo clean
        docker-compose -f docker-compose.coordinator.yml down -v
        docker-compose -f docker-compose.worker.yml down -v
        rm -rf ollama_data/ tailscale_data/ postgres_data/
        ;;
    
    "bench")
        echo -e "${GREEN}Running PoH benchmark...${NC}"
        cd coordinator
        python benchmark.py "test_seed_$(date +%s)"
        ;;
    
    "db-shell")
        echo -e "${GREEN}Opening database shell...${NC}"
        docker-compose -f docker-compose.coordinator.yml exec db psql -U troop_admin troop_ledger
        ;;
    
    "redis-cli")
        echo -e "${GREEN}Opening Redis CLI...${NC}"
        docker-compose -f docker-compose.coordinator.yml exec redis redis-cli
        ;;
    
    "help"|*)
        echo "Usage: ./dev.sh [command]"
        echo ""
        echo "Commands:"
        echo "  build       - Build Rust binaries (release)"
        echo "  check       - Run linters and checks"
        echo "  fmt         - Format all code"
        echo "  test        - Run all tests"
        echo "  coord       - Start coordinator stack"
        echo "  coord-logs  - Show coordinator logs"
        echo "  worker      - Start worker agent"
        echo "  client      - Start client proxy"
        echo "  clean       - Clean all build artifacts and data"
        echo "  bench       - Run PoH benchmark"
        echo "  db-shell    - Open PostgreSQL shell"
        echo "  redis-cli   - Open Redis CLI"
        echo "  help        - Show this message"
        ;;
esac
