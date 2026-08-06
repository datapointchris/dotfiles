#!/usr/bin/env bash
set -uo pipefail

# Documentation site operations shared by `dotfiles docs` and `task docs:*`.
# mkdocs is a project dependency rather than an installed binary, so it must run
# through `uv run` from the repo — plain `mkdocs` only resolves inside an
# activated venv.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export DOTFILES_DIR
export TERM=${TERM:-xterm}

source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"

usage() {
  help_header "docs"
  help_usage "docs.sh <serve|build|deploy>"

  help_section "Verbs"
  help_row "serve" "" "Serve the documentation site locally"
  help_row "build" "" "Build the static site, failing on any warning"
  help_row "deploy" "" "Publish the site to GitHub Pages"

  help_end
  exit "${1:-0}"
}

main() {
  local verb="${1:-}"
  [[ -z "$verb" || "$verb" == "help" || "$verb" == "-h" || "$verb" == "--help" ]] && usage 0

  cd "$DOTFILES_DIR" || exit 1

  case "$verb" in
    serve) uv run mkdocs serve ;;
    build) uv run mkdocs build --strict ;;
    deploy) uv run mkdocs gh-deploy --force ;;
    *)
      log_error "Unknown verb: $verb"
      usage 1
      ;;
  esac
}

main "$@"
