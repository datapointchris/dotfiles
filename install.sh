#!/bin/sh
# Bootstrap `dotfiles` onto a machine that has nothing.
#
# The one file in this repo that runs before anything is installed, which is why
# it is POSIX sh, sources nothing, and is short enough to read in full before
# running it. It stages an offline bundle if one is present, puts uv on the box,
# installs this repo as a uv tool, and hands over. Everything past the last line
# is Python.
#
#   ./install.sh --machine archlinux-personal-workstation
#   ./install.sh --machine wsl-work-workstation --offline
#
# It validates the manifest name itself, unlike every other check in the system,
# because the CLI that would answer the question does not exist yet.
set -eu

MACHINE="${MACHINE:-}"
OFFLINE=""
BUNDLE="${DOTFILES_BUNDLE:-$HOME/installers}"

die() {
  echo "install.sh: $*" >&2
  exit 1
}

require() {
  command -v "$1" >/dev/null || die "$1 is required — install it with the OS package manager, then re-run"
}

manifest_names() {
  for path in "$DOTFILES_DIR"/install/manifests/*.yml; do
    [ -f "$path" ] || continue
    name="${path##*/}"
    printf '  %s\n' "${name%.yml}"
  done
}

# Dated names sort as dates do, so the last match is the newest bundle for a
# given manifest and platform.
newest_bundle() {
  found=""
  for dir in . "$HOME"; do
    for path in "$dir"/dotfiles-offline-*.tar.gz; do
      if [ -f "$path" ]; then found="$path"; fi
    done
    if [ -n "$found" ]; then break; fi
  done
  printf '%s' "$found"
}

usage() {
  cat <<'EOF'
Usage: ./install.sh --machine NAME [--offline] [--through STAGE]

Puts uv and the dotfiles CLI on this machine, then runs `dotfiles apply`.
Selectors and every other flag belong to the CLI: `dotfiles apply --help`.

  --machine NAME   Which manifest this machine is (or set MACHINE)
  --offline        Stage the bundle from ./ or ~/ and install with no network
  --through STAGE  Converge only as far as this stage, and stop
EOF
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --machine)
      MACHINE="${2:-}"
      [ -n "$MACHINE" ] || die "--machine needs a manifest name"
      shift 2
      ;;
    --offline)
      OFFLINE=1
      shift
      ;;
    # Passed through for the same reason --offline is: the bootstrap has to reach
    # the CLI before any selector can be given, so a run that wants to stop part
    # way has no earlier place to say so. Both are about *this invocation* rather
    # than about which parts of the machine are wanted, which is the line the
    # message below draws.
    --through)
      THROUGH="${2:-}"
      [ -n "$THROUGH" ] || die "--through needs a stage name (dotfiles machines show names them)"
      shift 2
      ;;
    -h | --help) usage ;;
    *) die "unknown argument: $1 — phases and their flags live on \`dotfiles apply\`" ;;
  esac
done

if [ "$(id -u)" -eq 0 ] && [ "${DOTFILES_DOCKER_TEST:-}" != "true" ]; then
  die "do not run this as root"
fi

require git
require tar
DOTFILES_DIR=$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)

if [ -z "$MACHINE" ]; then
  echo "install.sh: --machine is required. Available manifests:" >&2
  manifest_names >&2
  exit 1
fi
if [ ! -f "$DOTFILES_DIR/install/manifests/$MACHINE.yml" ]; then
  echo "install.sh: no manifest named '$MACHINE'. Available:" >&2
  manifest_names >&2
  exit 1
fi

# Unpacked here rather than by `dotfiles bundle stage`, because the CLI that
# would run that verb is the thing the bundle exists to install.
if [ -n "$OFFLINE" ]; then
  archive=$(newest_bundle)
  if [ -n "$archive" ]; then
    echo "staging $archive"
    tar -xzf "$archive" -C "$HOME"
  fi
  [ -d "$BUNDLE" ] || die "offline: no bundle in ./ or ~/, and nothing staged at $BUNDLE"
fi

PATH="$HOME/.local/bin:$PATH"
export PATH

if ! command -v uv >/dev/null; then
  if [ -n "$OFFLINE" ]; then
    [ -x "$BUNDLE/bin/uv" ] || die "offline: the staged bundle carries no bin/uv"
    mkdir -p "$HOME/.local/bin"
    cp "$BUNDLE/bin/uv" "$HOME/.local/bin/uv"
  else
    require curl
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
fi

if [ -n "$OFFLINE" ]; then
  # Wheels from the bundle, and no interpreter download: uv resolves whichever
  # python already on the box satisfies requires-python, and says so when none
  # does. Nothing here second-guesses that — a wrong answer about the floor is
  # worse than uv's own error.
  set -- --offline --no-index --find-links "$BUNDLE/wheels" --no-python-downloads
else
  set --
fi

uv tool install "$@" --force --editable "$DOTFILES_DIR"

# uv reports success having written the entry point somewhere this shell cannot
# see it, when XDG_BIN_HOME points elsewhere. Catching it here names the cause;
# the alternative is `dotfiles: not found` from the exec below.
command -v dotfiles >/dev/null || die "installed, but 'dotfiles' is not on PATH — check \`uv tool dir --bin\`"

# Built up rather than branched over, so a third flag is one more `if` instead of
# another exec line. `if` and not `[ … ] &&`, because a false test there is a
# non-zero status and `set -e` above would take the script with it.
set -- apply --machine "$MACHINE"
if [ -n "$OFFLINE" ]; then
  set -- "$@" --offline
fi
if [ -n "${THROUGH:-}" ]; then
  set -- "$@" --through "$THROUGH"
fi
exec dotfiles "$@"
