# Common Installation Scripts

Cross-platform installer scripts organized by installation method. These scripts are called by `install.sh` via `run_installer()`.

## Directory Structure

```text
management/common/install/
├── github-releases/     # Install binaries from GitHub releases
├── fonts/               # Install Nerd Fonts and font families
├── language-managers/   # Install language version managers
├── language-tools/      # Install tools via language package managers
├── plugins/             # Install tmux/nvim/shell plugins
└── custom-installers/   # Tools with unique installation methods
```

Each category has its own README with specific examples and patterns.

## Installation Flow

```yaml
install.sh
    ↓ sources orchestration/run-installer.sh
run_installer()
    ↓ executes
installer script (e.g., github-releases/lazygit.sh)
    ↓ sources common/lib/ utilities
    - failure-logging.sh (error reporting)
    - github-release-installer.sh (GitHub release helpers)
    - font-installer.sh (font installation)
```

## Standard Installer Pattern

All installer scripts follow this pattern:

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
# + category-specific libraries

print_banner "Installing Tool"

# Idempotency check
if already_installed; then
  log_success "already installed"
  exit 0
fi

# Installation logic
if ! install_tool; then
  manual_steps="..."
  output_failure_data "tool" "$URL" "$VERSION" "$manual_steps" "Reason"
  log_error "Installation failed"
  exit 1
fi

log_success "Installation complete"
```

## Key Principles

**Idempotency**: All scripts check if already installed and exit 0 if so

**Error Reporting**: All scripts use `output_failure_data()` for structured failures

**Explicit Configuration**: Each script contains its own configuration inline (no complex YAML parsing)

**No set -e**: Scripts use explicit error checking (`if ! command; then`) instead of `set -e` to ensure `output_failure_data()` runs before exit

See individual category READMEs for specific examples and patterns.
