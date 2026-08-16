#!/bin/sh
# Bootstrap `dotfiles` onto a machine that has nothing.
#
# The one file in this repo that runs before anything is installed, which is why
# it is POSIX sh, sources nothing, and is short enough to read in full before
# running it. It stages an offline bundle if one is present, puts uv on the box,
# installs this repo as a uv tool, and stops — printing the `dotfiles` commands
# that converge the machine rather than running one.
#
#   ./install.sh --machine archlinux-personal-workstation
#   ./install.sh --machine wsl-work-workstation --offline
#
# It ended in `exec dotfiles apply` until a bare `./install.sh` on a WSL box whose
# `~/.env` already named it went straight into a half-hour networked run nobody
# had asked to start, and hung mid-download behind the work firewall with no plan
# ever having been shown. Getting the CLI onto a machine and converging that
# machine are separate decisions, so they are separate commands.
#
# It validates the manifest name itself, unlike every other check in the system,
# because the CLI that would answer the question does not exist yet.
set -eu

MACHINE="${MACHINE:-}"
OFFLINE=""
STAGING="${DOTFILES_BUNDLE:-${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/staged}"
BUNDLE=""

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

# Stamped names sort as time does, so the last match across every directory is
# the newest archive. Ranked across all of them rather than taking the first that
# holds any: a download writes into the cache, and no first-directory-wins order
# can rank that against a copy carried in beside the checkout.
newest_bundle() {
  # Sorted by basename and the last taken, rather than compared with `>`, which
  # POSIX leaves undefined for `[`. The name is emitted beside the path so the
  # ordering is the stamp's and not the directory's.
  for dir in "${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/bundles" . "$HOME"; do
    for path in "$dir"/dotfiles-offline-*.tar.gz; do
      if [ -f "$path" ]; then printf '%s\t%s\n' "${path##*/}" "$path"; fi
    done
  done | sort | tail -n 1 | cut -f2
}

# The newest staged bundle, which is the one the CLI's own resolver would read
# first. `bin/uv` and `wheels/` are the two things this script needs out of one,
# and both come from this bundle alone — there is no falling through to an older
# one here, which is safe only because `create_bundle.build` calls `add_uv` and
# `add_wheels` on every bundle, sparse included.
staged_bundle() {
  for path in "$STAGING"/*; do
    if [ -f "$path/manifest.txt" ]; then printf '%s\t%s\n' "${path##*/}" "$path"; fi
  done | sort | tail -n 1 | cut -f2
}

# Where one archive unpacks to: its name without the suffix. Named after the
# archive so a machine can say which bundle a staged file came from.
bundle_stem() {
  name="${1##*/}"
  printf '%s' "${name%.tar.gz}"
}

usage() {
  cat <<'EOF'
Usage: ./install.sh --machine NAME [--offline]

Puts uv and the dotfiles CLI on this machine and stops. Converging the machine
is `dotfiles apply`, which this prints and never runs; selectors and every other
flag belong to the CLI: `dotfiles apply --help`.

  --machine NAME   Which manifest this machine is (or set MACHINE)
  --offline        Stage the bundle from ./ or ~/ and install with no network
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
    # The one flag that is genuinely the bootstrap's: it decides where uv and the
    # wheels come from, which is decided before any CLI exists to be told. Every
    # other flag names something about converging the machine, and that command
    # is now typed separately.
    --offline)
      OFFLINE=1
      shift
      ;;
    -h | --help) usage ;;
    *) die "unknown argument: $1 — phases and their flags live on \`dotfiles apply\`, which this prints" ;;
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
    stem=$(bundle_stem "$archive")
    echo "staging $archive"
    # Into a scratch directory and moved, because the archive's single member is
    # named for the producer whatever the tarball is called — extracting in place
    # would land every bundle on one directory of that name.
    #
    # The member is found by its manifest rather than by its name, which is the
    # rule `offline_bundle.stage` uses. Naming it here made this the only reader
    # in the fleet that cared what the producer called it.
    #
    # The destination is removed after the extract succeeds, not before, so this
    # fails in the same order `offline_bundle.stage` does. Removing first means a
    # truncated archive reusing a name destroys the copy already staged under it,
    # on the one machine that cannot download another.
    rm -rf "$STAGING/.unpacking"
    mkdir -p "$STAGING/.unpacking"
    tar -xzf "$archive" -C "$STAGING/.unpacking"

    member=""
    for candidate in "$STAGING"/.unpacking/*/; do
      [ -d "$candidate" ] || continue
      [ -z "$member" ] || die "$archive carries more than one directory, so it is not a dotfiles bundle"
      member="${candidate%/}"
    done
    if [ -z "$member" ] || [ ! -f "$member/manifest.txt" ]; then
      die "$archive carries no manifest.txt, so it is not a dotfiles bundle"
    fi

    # The same refusal `offline_bundle.stage` makes, and this is the path that
    # needs it most: after the bootstrap something is always staged, so the CLI's
    # own check never runs again on this machine. A bundle naming no machine
    # stages, which is the rebuild state and the one that most needs to unpack.
    built_manifest=$(sed -n 's/.*"machine"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$member/bundle.json" 2>/dev/null | head -n 1)
    if [ -n "$built_manifest" ] && [ "$built_manifest" != "$MACHINE" ]; then
      rm -rf "$STAGING/.unpacking"
      die "$archive was built for $built_manifest and this machine is $MACHINE"
    fi

    # A sparse bundle omits what its premise says the target already had, and the
    # manifest above cannot check that premise: two machines share one, so the
    # comparison passes for the twin. The CLI compares `built_for` against this
    # box's discriminator, which is a hostname or a blake2b digest depending on a
    # coordinate declared in YAML — not a thing to resolve in POSIX sh.
    #
    # So the bootstrap takes full bundles only. A rebuild is the state where the
    # machine has least, which is the state a sparse bundle serves worst, and the
    # recovery is one command once the CLI it installs exists.
    completeness=$(sed -n 's/.*"completeness"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$member/bundle.json" 2>/dev/null | head -n 1)
    if [ "$completeness" = "sparse" ]; then
      rm -rf "$STAGING/.unpacking"
      die "$archive is sparse, and the bootstrap installs from a full bundle. Stage it after: dotfiles bundle stage $archive"
    fi

    rm -rf "$STAGING/${stem:?}"
    mv "$member" "$STAGING/$stem"
    # `rm -rf`, not `rmdir`: the member is discovered rather than named, so the
    # scratch directory legitimately holds whatever else the archive carried, and
    # under `set -eu` a non-empty one would kill the run after a correct stage.
    rm -rf "$STAGING/.unpacking"
  fi
  BUNDLE=$(staged_bundle)
  [ -n "$BUNDLE" ] || die "offline: no bundle in ${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/bundles, ./ or ~/, and nothing staged under $STAGING
  fetch one on a machine with a network: dotfiles bundle download"
fi

# Kept, because the hand-off at the bottom has to say whether the *next* shell
# will find the CLI. This script prepending a directory to its own PATH says
# nothing about the shell the person types the printed command into.
INHERITED_PATH="$PATH"
PATH="$HOME/.local/bin:$PATH"
export PATH

# Git Bash is the only shell this script meets on Windows, and `uname -s` answers
# `MINGW64_NT-…` there. MSYS_NT and CYGWIN_NT are the same family reached through
# a different emulation layer, and no Linux kernel reports any of the three.
#
# The list is written out here rather than shared with `coordinates.detect()`,
# which matches the same prefixes: this script imports nothing, which is the whole
# reason it is POSIX sh and readable in one sitting. Two sites deriving one fact
# is how they come to disagree, so `tests/shell/test_install_handover.py` asserts
# these two agree — a divergence then fails in CI rather than on the one box in
# the fleet nobody else can reach.
UV=uv
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) UV=uv.exe ;;
esac

if ! command -v uv >/dev/null; then
  if [ -n "$OFFLINE" ]; then
    [ -x "$BUNDLE/bin/$UV" ] || die "offline: the staged bundle carries no bin/$UV"
    mkdir -p "$HOME/.local/bin"
    cp "$BUNDLE/bin/$UV" "$HOME/.local/bin/$UV"
  elif [ "$UV" = uv.exe ]; then
    # astral publishes a PowerShell installer for Windows and a sh one for
    # everything else. The sh one is not a fallback: it fetches a Linux binary
    # that Git Bash will copy into place and then fail to run, which is a worse
    # outcome than not installing at all.
    require powershell
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
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
# the alternative is `dotfiles: not found` from a shell the person reaches later,
# with nothing left to say which run put it there.
ENTRY_POINT=$(command -v dotfiles) || die "installed, but 'dotfiles' is not on PATH — check \`uv tool dir --bin\`"
BIN_DIR=$(dirname -- "$ENTRY_POINT")

APPLY="--machine $MACHINE"
if [ -n "$OFFLINE" ]; then
  APPLY="$APPLY --offline"
fi

echo
echo "dotfiles is installed. Nothing else on this machine has changed yet."
echo
echo "Converge it with:"
echo
# Only where it is needed, and first, because it is the line without which the
# two below say `command not found` — uv writes the entry point to a directory a
# machine this fresh has no reason to have on PATH yet.
case ":$INHERITED_PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
echo "  dotfiles plan  --machine $MACHINE"
echo "  dotfiles apply $APPLY"
echo
echo "plan says what apply would change, and neither needs this script again."
echo "Stop part way with --through STAGE; dotfiles machines show $MACHINE names them."
