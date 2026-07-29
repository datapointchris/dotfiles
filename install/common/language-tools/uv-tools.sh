#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/uv-git-tools.sh"

# Check if uv is installed
if ! command -v uv &>/dev/null; then
  log_error "uv is not installed"
  echo "Install uv first:"
  echo "  macOS: brew install uv"
  echo "  Linux: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/install/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/install/packages.yml"
  exit 1
fi

MANIFEST_FLAG=()
if [[ -n "${MACHINE:-}" ]]; then
  MANIFEST_FLAG=(--manifest="$MACHINE")
fi

print_section "Python Tools (uv)"

# Get uv tools from packages.yml via Python parser
/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=uv "${MANIFEST_FLAG[@]}" | while read -r tool; do
  # Check if tool is already installed
  if uv tool list | grep -q "^$tool "; then
    log_success "$tool already installed, skipping"
  else
    log_info "Installing $tool..."
    if uv tool install "$tool"; then
      log_success "$tool installed"
    else
      log_warning "Failed to install $tool"
    fi
  fi
done

print_section "Git Python Tools (uv)"

/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" --type=git_uv "${MANIFEST_FLAG[@]}" | while IFS='|' read -r name repo ref_mode; do
  if uv tool list | grep -q "^$name "; then
    log_success "$name already installed, skipping"
    continue
  fi

  # A release install is pinned to its tag so the tool's own updater will work
  # on it at all; only a repo publishing no releases follows its branch.
  requirement="$repo"
  if [[ "$ref_mode" == "release" ]]; then
    if ref=$(uv_git_tool_latest_ref "$repo"); then
      requirement=$(uv_git_tool_requirement "$name" "$repo" "$ref")
    else
      log_warning "$name: no release found, installing from the default branch (its own update will refuse to run)"
    fi
  fi

  log_info "Installing $name from $requirement..."
  if uv tool install "$requirement"; then
    log_success "$name installed"
  else
    log_warning "Failed to install $name"
  fi
done
