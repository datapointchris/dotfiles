#!/usr/bin/env bash
set -uo pipefail

# doit's cards and Labs are a repo of their own, authored far more often than
# doit is released. doit reads them from $XDG_DATA_HOME/doit and clones them
# there itself on a machine that has none — which is all a read-only machine
# ever needs.
#
# A machine that *authors* cards needs the checkout somewhere git is used, so
# this points the installed path at the source rather than making a second copy.
# Two real copies would mean a card is unreadable until it has gone commit →
# push → sync, a round trip through GitHub to read a file you just wrote.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

REPO=$(/usr/bin/python3 "$DOTFILES_DIR/install/parse_packages.py" \
  --custom-installer doit-content --field repo) \
  || {
    echo "Error: could not read doit-content.repo from packages.yml" >&2
    exit 1
  }

REPO_URL="https://github.com/$REPO.git"
SOURCE_DIR="$HOME/tools/doit-content"
INSTALL_LINK="$HOME/.local/share/doit"

if [[ "${1:-}" == "--update" ]]; then
  source "$DOTFILES_DIR/install/common/lib/missing-tools.sh"
  if ! command -v doit >/dev/null 2>&1; then
    skip_update_for_absent_tool "doit"
  fi
  doit content sync
  exit $?
fi

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  log_info "Cloning doit-content to $SOURCE_DIR..."
  mkdir -p "$(dirname "$SOURCE_DIR")"
  if ! clone_output=$(git clone --quiet "$REPO_URL" "$SOURCE_DIR" 2>&1); then
    output_failure_data "doit-content" "$REPO_URL" "latest" "Clone failed" "$clone_output"
    log_error "doit-content clone failed"
    exit 1
  fi
fi

if [[ -L "$INSTALL_LINK" ]]; then
  if [[ "$(readlink "$INSTALL_LINK")" == "$SOURCE_DIR" ]]; then
    log_success "doit-content already linked: $INSTALL_LINK -> $SOURCE_DIR"
    exit 0
  fi
  rm "$INSTALL_LINK"
fi

# doit clones here on first run, so a real checkout at the installed path is the
# expected state on a machine that read cards before this installer ran. It is
# replaceable once it holds nothing the source does not — uncommitted work here
# is invisible to every `git status` that would otherwise find it, which is the
# whole reason for the link, so say where it is rather than deleting it.
if [[ -d "$INSTALL_LINK" ]]; then
  if [[ ! -d "$INSTALL_LINK/.git" ]]; then
    output_failure_data "doit-content" "$REPO_URL" "latest" \
      "$INSTALL_LINK exists and is not a checkout — move it aside and re-run"
    log_error "doit-content: $INSTALL_LINK is an unexpected directory"
    exit 1
  fi
  if [[ -n "$(git -C "$INSTALL_LINK" status --porcelain)" ]]; then
    output_failure_data "doit-content" "$REPO_URL" "latest" \
      "Uncommitted cards in $INSTALL_LINK — commit or move them, then re-run"
    log_error "doit-content: uncommitted work in $INSTALL_LINK"
    exit 1
  fi
  rm -rf "$INSTALL_LINK"
fi

mkdir -p "$(dirname "$INSTALL_LINK")"
if ln -s "$SOURCE_DIR" "$INSTALL_LINK"; then
  log_success "doit-content linked: $INSTALL_LINK -> $SOURCE_DIR"
else
  output_failure_data "doit-content" "$REPO_URL" "latest" "Could not create symlink"
  log_error "doit-content link failed"
  exit 1
fi
