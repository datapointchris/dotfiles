#!/usr/bin/env bash
# Test connectivity to all URLs used during dotfiles installation
# Run this on a restricted network to identify what's blocked
#
# Usage: bash test-connectivity.sh [output-file]
# Default output: management/offline/connectivity-results.txt (in dotfiles repo)
#
# After running, commit and push the results:
#   git add management/offline/connectivity-results.txt
#   git commit -m "Add connectivity test results from WSL"
#   git push

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${1:-$SCRIPT_DIR/connectivity-results.txt}"
TIMEOUT=10

# Colors for terminal (won't affect file output)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

passed=0
failed=0
results=()

test_url() {
    local name="$1"
    local url="$2"
    local method="${3:-HEAD}"

    # Use HEAD request by default (faster, no download)
    # Some servers don't support HEAD, fall back to GET with range
    if [[ "$method" == "HEAD" ]]; then
        if curl -fsSL --head --connect-timeout "$TIMEOUT" "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $name"
            results+=("YES | $name | $url")
            ((passed++))
            return 0
        fi
    fi

    # Try GET with range header (downloads only first byte)
    if curl -fsSL --connect-timeout "$TIMEOUT" -r 0-0 "$url" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name"
        results+=("YES | $name | $url")
        ((passed++))
        return 0
    fi

    echo -e "${RED}✗${NC} $name"
    results+=("NO  | $name | $url")
    ((failed++))
    return 1
}

test_git_clone() {
    local name="$1"
    local repo="$2"

    # Test git ls-remote (checks connectivity without cloning)
    if git ls-remote --quiet "$repo" HEAD >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name"
        results+=("YES | $name | $repo")
        ((passed++))
        return 0
    fi

    echo -e "${RED}✗${NC} $name"
    results+=("NO  | $name | $repo")
    ((failed++))
    return 1
}

echo "======================================"
echo "Dotfiles Connectivity Test"
echo "======================================"
echo "Testing from: $(hostname)"
echo "Date: $(date)"
echo "Output file: $OUTPUT_FILE"
echo ""

# --- GitHub Releases ---
echo -e "${YELLOW}GitHub Releases:${NC}"
test_url "neovim" "https://github.com/neovim/neovim/releases/download/v0.10.0/nvim-linux64.tar.gz"
test_url "lazygit" "https://github.com/jesseduffield/lazygit/releases/download/v0.44.1/lazygit_0.44.1_Linux_x86_64.tar.gz"
test_url "yazi" "https://github.com/sxyazi/yazi/releases/latest"
test_url "fzf" "https://github.com/junegunn/fzf/releases/latest"
test_url "glow" "https://github.com/charmbracelet/glow/releases/latest"
test_url "duf" "https://github.com/muesli/duf/releases/latest"
test_url "shellcheck" "https://github.com/koalaman/shellcheck/releases/latest"
test_url "tflint" "https://github.com/terraform-linters/tflint/releases/latest"
test_url "trivy" "https://github.com/aquasecurity/trivy/releases/latest"
test_url "zk" "https://github.com/zk-org/zk/releases/latest"
echo ""

# --- GitHub API ---
echo -e "${YELLOW}GitHub API:${NC}"
test_url "github-api-releases" "https://api.github.com/repos/neovim/neovim/releases/latest" "GET"
echo ""

# --- Raw GitHub Content ---
echo -e "${YELLOW}Raw GitHub Content (install scripts):${NC}"
test_url "theme-install" "https://raw.githubusercontent.com/datapointchris/theme/main/install.sh"
test_url "font-install" "https://raw.githubusercontent.com/datapointchris/font/main/install.sh"
test_url "nvm-install" "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh"
test_url "homebrew-install" "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
echo ""

# --- Git Clone ---
echo -e "${YELLOW}Git Clone (git protocol):${NC}"
test_git_clone "github-dotfiles" "https://github.com/datapointchris/dotfiles.git"
test_git_clone "github-theme" "https://github.com/datapointchris/theme.git"
test_git_clone "github-tpm" "https://github.com/tmux-plugins/tpm.git"
test_git_clone "github-zsh-syntax" "https://github.com/zsh-users/zsh-syntax-highlighting.git"
test_git_clone "github-bats-core" "https://github.com/bats-core/bats-core.git"
echo ""

# --- Nerd Fonts ---
echo -e "${YELLOW}Nerd Fonts:${NC}"
test_url "nerd-fonts-releases" "https://github.com/ryanoasis/nerd-fonts/releases/latest"
test_url "nerd-fonts-jetbrains" "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/JetBrainsMono.tar.xz"
echo ""

# --- Other Fonts ---
echo -e "${YELLOW}Other Font Sources:${NC}"
test_url "victor-mono" "https://github.com/rubjo/victor-mono/releases/latest"
test_url "iosevka" "https://github.com/be5invis/Iosevka/releases/latest"
echo ""

# --- Language Installers ---
echo -e "${YELLOW}Language Runtime Installers:${NC}"
test_url "go-download" "https://go.dev/dl/go1.22.0.linux-amd64.tar.gz"
test_url "go-version-api" "https://go.dev/VERSION?m=text" "GET"
test_url "rustup" "https://sh.rustup.rs" "GET"
test_url "uv-install" "https://astral.sh/uv/install.sh"
echo ""

# --- Go Module Proxy ---
echo -e "${YELLOW}Go Module Proxy (go install):${NC}"
test_url "go-proxy-task" "https://proxy.golang.org/github.com/go-task/task/v3/@latest" "GET"
test_url "go-proxy-gum" "https://proxy.golang.org/github.com/charmbracelet/gum/@latest" "GET"
test_url "go-proxy-lazydocker" "https://proxy.golang.org/github.com/jesseduffield/lazydocker/@latest" "GET"
echo ""

# --- Go Tools as GitHub Releases ---
echo -e "${YELLOW}Go Tools (GitHub Releases alternative):${NC}"
test_url "task-release" "https://github.com/go-task/task/releases/latest"
test_url "gum-release" "https://github.com/charmbracelet/gum/releases/latest"
test_url "lazydocker-release" "https://github.com/jesseduffield/lazydocker/releases/latest"
test_url "cheat-release" "https://github.com/cheat/cheat/releases/latest"
test_url "terraform-docs-release" "https://github.com/terraform-docs/terraform-docs/releases/latest"
test_url "actionlint-release" "https://github.com/rhysd/actionlint/releases/latest"
test_url "goose-release" "https://github.com/pressly/goose/releases/latest"
test_url "gofumpt-release" "https://github.com/mvdan/gofumpt/releases/latest"
test_url "gdu-release" "https://github.com/dundee/gdu/releases/latest"
echo ""

# --- Package Registries ---
echo -e "${YELLOW}Package Registries:${NC}"
test_url "npm-registry" "https://registry.npmjs.org/typescript/latest" "GET"
test_url "pypi" "https://pypi.org/simple/ruff/" "GET"
test_url "crates-io" "https://crates.io/api/v1/crates/bat" "GET"
echo ""

# --- Other Tools ---
echo -e "${YELLOW}Other Tools:${NC}"
test_url "awscli-linux" "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
test_url "terraform-releases" "https://releases.hashicorp.com/terraform-ls/" "GET"
echo ""

# --- Write results to file ---
{
    echo "======================================"
    echo "Dotfiles Connectivity Test Results"
    echo "======================================"
    echo "Host: $(hostname)"
    echo "Date: $(date)"
    echo "User: $(whoami)"
    echo ""
    echo "Summary: $passed passed, $failed failed"
    echo ""
    echo "Results:"
    echo "--------------------------------------"
    printf '%s\n' "${results[@]}"
    echo "--------------------------------------"
    echo ""
    echo "Legend: YES = accessible, NO = blocked/failed"
} > "$OUTPUT_FILE"

echo ""
echo "======================================"
echo -e "Summary: ${GREEN}$passed passed${NC}, ${RED}$failed failed${NC}"
echo "======================================"
echo ""
echo "Results written to: $OUTPUT_FILE"
echo ""
echo "Copy the output file to review results:"
echo "  cat $OUTPUT_FILE"
