#!/bin/bash
# Monkey Troop Installation Script

set -e

REPO="monkeytroop/monkey-troop"
INSTALL_DIR="$HOME/.monkey-troop"
BIN_DIR="$HOME/.local/bin"

echo "🐒 Monkey Troop Installer"
echo "========================"
echo ""

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux*)     PLATFORM="linux";;
    Darwin*)    PLATFORM="macos";;
    *)          echo "Unsupported OS: $OS"; exit 1;;
esac

case "$ARCH" in
    x86_64)     ARCH="amd64";;
    aarch64)    ARCH="arm64";;
    arm64)      ARCH="arm64";;
    *)          echo "Unsupported architecture: $ARCH"; exit 1;;
esac

echo "Detected platform: $PLATFORM-$ARCH"
echo ""

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Download latest release (placeholder - adjust when releases are available)
echo "📥 Downloading latest release..."
DOWNLOAD_URL="https://github.com/$REPO/releases/latest/download/monkey-troop-$PLATFORM-$ARCH.tar.gz"

if command -v curl >/dev/null 2>&1; then
    curl -L "$DOWNLOAD_URL" -o "$INSTALL_DIR/monkey-troop.tar.gz" || {
        echo "⚠️  Release not yet available. Please build from source:"
        echo "   git clone https://github.com/$REPO.git"
        echo "   cd monkey-troop"
        echo "   cargo build --release"
        exit 1
    }
elif command -v wget >/dev/null 2>&1; then
    wget "$DOWNLOAD_URL" -O "$INSTALL_DIR/monkey-troop.tar.gz" || {
        echo "⚠️  Release not yet available. Please build from source."
        exit 1
    }
else
    echo "❌ Neither curl nor wget found. Please install one."
    exit 1
fi

# Extract
echo "📦 Extracting..."
tar -xzf "$INSTALL_DIR/monkey-troop.tar.gz" -C "$INSTALL_DIR"

# Install binaries
echo "🔧 Installing binaries to $BIN_DIR..."
cp "$INSTALL_DIR/monkey-troop-worker" "$BIN_DIR/"
cp "$INSTALL_DIR/monkey-troop-client" "$BIN_DIR/"
chmod +x "$BIN_DIR/monkey-troop-worker"
chmod +x "$BIN_DIR/monkey-troop-client"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "⚠️  Add to your PATH by running:"
    echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Install Tailscale: https://tailscale.com/download"
echo "  2. Connect to network: tailscale up --login-server=https://troop.100monkeys.ai"
echo "  3. Start worker: monkey-troop-worker"
echo "  4. Or start client: monkey-troop-client up"
echo ""
echo "Documentation: https://github.com/$REPO"
