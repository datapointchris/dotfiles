#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

# Parse arguments
FORCE_INSTALL=false
UPDATE_MODE=false
if [[ "${1:-}" == "--force" ]]; then
  FORCE_INSTALL=true
elif [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

# Check if Go is installed
if ! command -v go &>/dev/null; then
  log_error "Go is not installed"
  echo "Install Go first: bash $DOTFILES_DIR/management/common/install/language-managers/install-go.sh"
  exit 1
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

print_header "Go Tools"

# Get Go tools from packages.yml via Python parser
GOBIN="$HOME/go/bin"

FAILURE_COUNT=0
INSTALLED_COUNT=0
SKIPPED_COUNT=0

get_tool_version() {
  local bin="$1"
  local ver=""
  ver=$("$bin" --version 2>&1 | grep -oE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1) ||
    ver=$("$bin" version 2>&1 | grep -oE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1) ||
    ver=""
  echo "$ver"
}

while read -r tool; do
  # Extract binary name from tool path (last segment after /)
  binary_name="${tool##*/}"
  binary_path="$GOBIN/$binary_name"

  # Check if already installed (unless --force or --update)
  if [[ -f "$binary_path" ]] && [[ "$FORCE_INSTALL" != "true" ]] && [[ "$UPDATE_MODE" != "true" ]]; then
    log_success "$binary_name already installed, skipping"
    SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    continue
  fi

  # Get version before update (if updating)
  version_before=""
  if [[ "$UPDATE_MODE" == "true" ]] && [[ -f "$binary_path" ]]; then
    version_before=$(get_tool_version "$binary_path")
  fi

  # Install/update the tool
  if [[ "$UPDATE_MODE" == "true" ]]; then
    log_info "Updating $binary_name..."
  else
    log_info "Installing $binary_name..."
  fi
  go install "$tool@latest" 2>&1 | grep -v "go: downloading" || true

  # Check if binary was actually created
  if [[ -f "$binary_path" ]]; then
    version_after=$(get_tool_version "$binary_path")
    if [[ "$UPDATE_MODE" == "true" ]]; then
      if [[ -n "$version_before" ]] && [[ -n "$version_after" ]]; then
        if [[ "$version_before" == "$version_after" ]]; then
          log_success "$binary_name already at latest ($version_after)"
        else
          log_success "$binary_name updated: $version_before → $version_after"
        fi
      elif [[ -n "$version_after" ]]; then
        # Had no version before (new install during update mode)
        log_success "$binary_name installed ($version_after)"
      elif [[ -n "$version_before" ]]; then
        # Can't get version after (parsing changed?)
        log_success "$binary_name updated (was $version_before, version now unparseable)"
      else
        # Can't get any version - note this explicitly
        log_success "$binary_name reinstalled (version unknown)"
      fi
    else
      if [[ -n "$version_after" ]]; then
        log_success "$binary_name installed ($version_after)"
      else
        log_success "$binary_name installed (version unknown)"
      fi
    fi
    INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
  else
    manual_steps="Install manually with go:
   go install $tool@latest

Tool will be installed to:
   $GOBIN"

    output_failure_data "$tool" "https://pkg.go.dev/$tool" "latest" "$manual_steps" "Failed to install via go install"
    log_warning "Failed to install $binary_name (see summary)"
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
  fi
done < <(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=go)

if [[ $FAILURE_COUNT -gt 0 ]]; then
  log_warning "$FAILURE_COUNT tool(s) failed to install"
  exit 1
fi
