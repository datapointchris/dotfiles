#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/install/common/lib/installed-versions.sh"
source "$DOTFILES_DIR/install/common/lib/package-query.sh"
source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"

FORCE_INSTALL="${FORCE_INSTALL:-false}"
UPDATE_MODE="${UPDATE_MODE:-false}"

# Copy to temp then rename: a plain cp over a binary that is currently running
# fails with "text file busy".
install_go_binary_from_cache() {
  local cached_binary="$1" binary_path="$2"

  [[ -f "$cached_binary" ]] || return 1
  mkdir -p "$(dirname "$binary_path")"
  cp "$cached_binary" "${binary_path}.new"
  chmod +x "${binary_path}.new"
  mv "${binary_path}.new" "$binary_path"
}

# Puts $tool at $binary_path from the offline bundle or the module proxy, leaving
# go's output in GO_INSTALL_OUTPUT for the failure report — behind the work
# firewall the TLS error it prints there is the entire diagnosis.
#
# An install prefers the bundle; an update prefers the proxy, because a bundle
# laid down months ago is exactly what the update is trying to move past. The
# update still falls back to the bundle when the proxy is unreachable: on a
# firewalled machine it never is, and without the fallback every Go tool stays
# pinned at the version the machine was first built with while a current bundle
# sits unused on disk.
install_go_tool() {
  local tool="$1" binary_path="$2" cached_binary="$3"
  local go_output install_status=0

  GO_INSTALL_OUTPUT=""

  if [[ "$UPDATE_MODE" != "true" ]] && [[ -f "$cached_binary" ]]; then
    log_info "Using cached binary: $cached_binary"
    install_go_binary_from_cache "$cached_binary" "$binary_path" || install_status=$?
    return $install_status
  fi

  # The exit status must be captured separately: an update leaves the previous
  # binary in place, so its existence alone would report a failed install as
  # "already at latest".
  go_output=$(mktemp)
  go install "$tool@latest" >"$go_output" 2>&1 || install_status=$?
  GO_INSTALL_OUTPUT=$(grep -v "go: downloading" "$go_output" || true)
  rm -f "$go_output"
  if [[ -n "$GO_INSTALL_OUTPUT" ]]; then
    echo "$GO_INSTALL_OUTPUT"
  fi

  if [[ $install_status -ne 0 ]] && [[ -f "$cached_binary" ]]; then
    log_info "go install unreachable — updating from the bundle: $cached_binary"
    if install_go_binary_from_cache "$cached_binary" "$binary_path"; then
      install_status=0
    fi
  fi

  return $install_status
}

# Install only when executed, never when sourced — unit tests source this file to
# call install_go_tool directly. Guarding on the condition rather than an opt-in
# env var leaves nothing for a caller to forget.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ "${1:-}" == "--force" ]]; then
    FORCE_INSTALL=true
  elif [[ "${1:-}" == "--update" ]]; then
    UPDATE_MODE=true
  fi

  # Ensure the Go toolchain is on PATH. Non-interactive callers (cron, scripts) don't
  # source .zshrc, which is where /usr/local/go/bin is added, so `go install` below
  # would fail. Mirror go.sh's fallback to the standard install location.
  if ! command -v go &>/dev/null; then
    if [[ -x "/usr/local/go/bin/go" ]]; then
      export PATH="/usr/local/go/bin:$PATH"
    else
      log_error "Go is not installed"
      echo "Install Go first: bash $DOTFILES_DIR/install/common/language-managers/go.sh"
      exit 1
    fi
  fi

  if [[ ! -f "$DOTFILES_DIR/install/packages.yml" ]]; then
    log_error "packages.yml not found at $DOTFILES_DIR/install/packages.yml"
    exit 1
  fi

  init_package_filters

  print_header "Go Tools"

  GOBIN="$HOME/go/bin"

  FAILURE_COUNT=0
  INSTALLED_COUNT=0
  SKIPPED_COUNT=0

  while IFS='|' read -r binary_name tool; do
    binary_path="$GOBIN/$binary_name"

    # Check if already installed (unless --force or --update)
    if [[ -f "$binary_path" ]] && [[ "$FORCE_INSTALL" != "true" ]] && [[ "$UPDATE_MODE" != "true" ]]; then
      log_success "$binary_name already installed, skipping"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      continue
    fi

    # `go install @latest` builds whether or not the binary exists, so an update
    # would otherwise create tools it was never asked to install.
    if [[ ! -f "$binary_path" ]] && [[ "$UPDATE_MODE" == "true" ]]; then
      log_warning "$binary_name not installed — skipping update"
      record_missing_tool "$binary_name" "go-tools"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      continue
    fi

    # Get version before update (if updating)
    version_before=""
    if [[ "$UPDATE_MODE" == "true" ]] && [[ -f "$binary_path" ]]; then
      version_before=$(go_binary_module_version "$binary_path") || version_before=""
    fi

    if [[ "$UPDATE_MODE" == "true" ]]; then
      log_info "Updating $binary_name..."
    else
      log_info "Installing $binary_name..."
    fi

    install_status=0
    install_go_tool "$tool" "$binary_path" "$HOME/installers/go-binaries/$binary_name" || install_status=$?

    if [[ -f "$binary_path" ]] && [[ $install_status -eq 0 ]]; then
      version_after=$(go_binary_module_version "$binary_path") || version_after=""
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
      reason="Failed to install via go install"
      if [[ -f "$binary_path" ]]; then
        reason="go install failed; $binary_name left at the previously installed version"
      fi

      output_failure_data "$tool" "https://pkg.go.dev/$tool" "latest" "$reason" "$GO_INSTALL_OUTPUT"
      log_warning "Failed to install $binary_name (see summary)"
      FAILURE_COUNT=$((FAILURE_COUNT + 1))
    fi
  done < <(parse_packages --type=go --format=name_package)

  if [[ $FAILURE_COUNT -gt 0 ]]; then
    log_warning "$FAILURE_COUNT tool(s) failed to install"
    exit 1
  fi
fi
