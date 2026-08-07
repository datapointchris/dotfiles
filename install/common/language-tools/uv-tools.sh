#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/uv-git-tools.sh"
source "$DOTFILES_DIR/install/common/lib/package-query.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

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

init_package_filters

# Both loops read through process substitution rather than a pipe, and the script
# exits on the tally. Behind a pipe the loop body ran in a subshell, so no count
# survived it and the script's status was the last iteration's — indy failed to
# install (a private repo with no credentials in the container), safekeep
# succeeded after it, uv-tools.sh exited 0, and run_installer discarded the
# captured stderr along with the warning. The phase reported success and the tool
# was simply absent. Only the manifest-derived verification noticed.
FAILED_TOOL_COUNT=0

print_section "Python Tools (uv)"

while read -r tool; do
  if uv tool list | grep -q "^$tool "; then
    log_success "$tool already installed, skipping"
    continue
  fi

  log_info "Installing $tool..."
  if uv tool install "$tool"; then
    log_success "$tool installed"
  else
    log_error "Failed to install $tool"
    output_failure_data "$tool" "pypi:$tool" "latest" "uv tool install failed"
    FAILED_TOOL_COUNT=$((FAILED_TOOL_COUNT + 1))
  fi
done < <(parse_packages --type=uv)

print_section "Git Python Tools (uv)"

while IFS='|' read -r name repo ref_mode; do
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
    log_error "Failed to install $name"
    output_failure_data "$name" "$repo" "${ref:-unknown}" "uv tool install failed (a private repo needs git credentials)"
    FAILED_TOOL_COUNT=$((FAILED_TOOL_COUNT + 1))
  fi
done < <(parse_packages --type=git_uv)

[[ $FAILED_TOOL_COUNT -eq 0 ]] || exit 1
