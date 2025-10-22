#!/bin/bash

# Corporate Firewall LSP Installation Script
# This script installs language servers manually when Mason is blocked

set -e

echo "🚀 Installing Language Servers (Corporate Firewall Workaround)"
echo "=================================================="

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install via package manager
install_package() {
    local package="$1"
    local method="$2"

    echo "📦 Installing $package via $method..."

    case "$method" in
        "brew")
            if command_exists brew; then
                brew install "$package"
            else
                echo "❌ Homebrew not installed"
                return 1
            fi
            ;;
        "npm")
            if command_exists npm; then
                npm install -g "$package"
            else
                echo "❌ npm not installed"
                return 1
            fi
            ;;
        "pip")
            if command_exists pip; then
                pip install --user "$package"
            else
                echo "❌ pip not installed"
                return 1
            fi
            ;;
        "apt")
            if command_exists apt; then
                sudo apt update && sudo apt install -y "$package"
            else
                echo "❌ apt not available"
                return 1
            fi
            ;;
        "manual")
            echo "⚠️  Manual installation required for $package"
            echo "   See: https://github.com/search?q=$package+language+server"
            ;;
    esac
}

# Core Language Servers
echo ""
echo "🔧 Installing Core Language Servers..."

if [[ "$OS" == "macos" ]]; then
    # macOS installations
    install_package "lua-language-server" "brew"
    install_package "bash-language-server" "npm"
    install_package "typescript-language-server" "npm"
    install_package "typescript" "npm"
    install_package "vscode-langservers-extracted" "npm"  # html, css, json, eslint
    install_package "basedpyright" "brew"
    install_package "ruff" "brew"
    install_package "gopls" "brew"
    install_package "rust-analyzer" "brew"
    install_package "dockerfile-language-server-nodejs" "npm"
    install_package "@microsoft/compose-language-service" "npm"
    install_package "terraform-ls" "brew"
    install_package "tflint" "brew"
    install_package "marksman" "brew"
    install_package "taplo" "brew"
    install_package "sql-language-server" "npm"
    install_package "vim-language-server" "npm"

elif [[ "$OS" == "linux" ]]; then
    # Linux installations
    install_package "nodejs" "apt"
    install_package "npm" "apt"

    # npm-based servers
    install_package "bash-language-server" "npm"
    install_package "typescript-language-server" "npm"
    install_package "typescript" "npm"
    install_package "vscode-langservers-extracted" "npm"
    install_package "dockerfile-language-server-nodejs" "npm"
    install_package "@microsoft/compose-language-service" "npm"
    install_package "sql-language-server" "npm"
    install_package "vim-language-server" "npm"

    # Python tools
    install_package "basedpyright" "pip"
    install_package "ruff" "pip"

    # Manual installations needed
    install_package "lua-language-server" "manual"
    install_package "gopls" "manual"
    install_package "rust-analyzer" "manual"
    install_package "terraform-ls" "manual"
    install_package "tflint" "manual"
    install_package "marksman" "manual"
    install_package "taplo" "manual"
fi

echo ""
echo "🎉 Installation Complete!"
echo ""
echo "📋 Verification Commands:"
echo "========================="

# Verification commands
servers=(
    "lua-language-server:lua-language-server --version"
    "bash-language-server:bash-language-server --version"
    "typescript-language-server:typescript-language-server --version"
    "basedpyright:basedpyright --version"
    "ruff:ruff --version"
    "gopls:gopls version"
    "rust-analyzer:rust-analyzer --version"
    "terraform-ls:terraform-ls --version"
    "marksman:marksman --version"
    "taplo:taplo --version"
)

for server_info in "${servers[@]}"; do
    IFS=':' read -r server_name command <<< "$server_info"
    echo "• $server_name: $command"
done

echo ""
echo "🔧 Manual Installation Notes:"
echo "============================="
echo "For servers marked as 'manual', download from:"
echo "• Lua Language Server: https://github.com/LuaLS/lua-language-server/releases"
echo "• Go Language Server: go install golang.org/x/tools/gopls@latest"
echo "• Rust Analyzer: rustup component add rust-analyzer"
echo "• Terraform LS: https://releases.hashicorp.com/terraform-ls/"
echo "• TFLint: https://github.com/terraform-linters/tflint/releases"
echo "• Marksman: https://github.com/artempyanykh/marksman/releases"
echo "• Taplo: cargo install taplo-cli --locked"

echo ""
echo "📚 Next Steps:"
echo "=============="
echo "1. Restart Neovim"
echo "2. Check LSP status with :LspInfo"
echo "3. Run health check with :checkhealth vim.lsp"
echo "4. See full installation guide: docs/lsp.md"

echo ""
echo "💡 Pro Tip: This config uses native LSP, so no Mason required!"
