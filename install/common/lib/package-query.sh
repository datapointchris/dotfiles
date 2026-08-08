#!/usr/bin/env bash

# Builds the packages.yml query narrowing that every installer and updater shares.
#
# Source after logging.sh with DOTFILES_DIR set, then call init_package_filters
# once MACHINE and PACKAGE_OWNER are known. The two-step exists because
# install.sh and update.sh only learn the owner after parsing their arguments,
# while the standalone tool scripts read both straight from the environment.
#
# The manifest and owner narrowings used to be hand-rolled in four tool scripts
# plus update.sh, and they had drifted: only go-tools.sh read PACKAGE_OWNER, so
# `--mine` ran cargo, uv, and npm in full while claiming to filter.

PACKAGE_FILTER_FLAGS=()

init_package_filters() {
  PACKAGE_FILTER_FLAGS=()

  if [[ -n "${MACHINE:-}" ]]; then
    if [[ -f "$DOTFILES_DIR/install/manifests/${MACHINE}.yml" ]]; then
      PACKAGE_FILTER_FLAGS+=(--manifest="$MACHINE")
    else
      log_warning "Manifest not found for MACHINE=$MACHINE — every package in packages.yml is in scope"
    fi
  fi

  if [[ -n "${PACKAGE_OWNER:-}" ]]; then
    PACKAGE_FILTER_FLAGS+=(--owner="$PACKAGE_OWNER")
  fi
}

parse_packages() {
  PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.parse_packages "$@" "${PACKAGE_FILTER_FLAGS[@]}"
}

# True when the current narrowing leaves at least one entry for this query.
# Gating a phase on this rather than on the raw manifest key is what makes
# --mine skip a toolchain whose tools all belong to someone else.
packages_present() {
  local output
  output=$(parse_packages "$@" 2>/dev/null) || return 1
  [[ -n "$output" ]]
}
