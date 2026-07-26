#!/usr/bin/env bash
set -uo pipefail

# Documentation site operations shared by `dotfiles docs` and `task docs:*`.
# mkdocs is a project dependency rather than an installed binary, so it must run
# through `uv run` from the repo — plain `mkdocs` only resolves inside an
# activated venv.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$OPS_DIR/../.." && pwd)"
export DOTFILES_DIR

usage() {
  echo "Usage: docs.sh <serve|build|deploy>"
  echo ""
  echo "  serve    Serve the documentation site locally"
  echo "  build    Build the static site, failing on any warning"
  echo "  deploy   Publish the site to GitHub Pages"
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
    echo "Unknown verb: $verb" >&2
    usage 1
    ;;
  esac
}

main "$@"
