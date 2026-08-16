#!/usr/bin/env bash
# The transport the e2e declares, standing where `ifiles` stands on a real machine.
#
# dotfiles never learns what this is. It reads a program name and an argv per
# operation out of `[remote.transport]` and runs them, so a script implementing
# the same six operations exercises every line of `src/dotfiles/remote.py` — the
# probe, the listing contract, the digest check around push and pull, and the
# refusals. What it must not be is a mock: this really moves bytes between two
# containers over ssh, and stopping the peer really makes it unreachable.
#
# Paths arrive absolute. `Remote.directory` joins the configured root with the
# shelf and the manifest, so `{dir}` is already `/srv/shelf/bundles/<manifest>`
# and `{remote}` is a full path to one file.

set -euo pipefail

HOST_FILE=/etc/shelf-host

# From a file rather than the environment. `Machine.exec` runs `bash -c`, which
# is non-interactive and reads no profile, so an export written to `.bashrc`
# never reaches this — and the failure is a transport that cannot resolve its
# peer while every config in sight looks right.
SHELF_HOST="${SHELF_HOST:-$(cat "$HOST_FILE" 2>/dev/null || true)}"
: "${SHELF_HOST:?no shelf host: set SHELF_HOST or write one to $HOST_FILE}"

# BatchMode so a missing key fails instead of prompting, and a short timeout so
# an unreachable peer answers inside the probe's own backoff rather than hanging
# the run. StrictHostKeyChecking off because the peer is rebuilt every session
# and its key is new each time.
SSH_OPTIONS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o LogLevel=ERROR
  -o ConnectTimeout=5
)

operation="${1:?an operation is required}"
shift

case "$operation" in
  # Must succeed whenever the peer answers, whatever is or is not stored on it.
  # A listing of the root cannot serve: a root that does not exist yet is the
  # ordinary state of a fresh shelf, and that would report a working server down.
  probe)
    exec ssh "${SSH_OPTIONS[@]}" "$SHELF_HOST" true
    ;;
  # One name per line on stdout, which is the whole contract. Fails where the
  # directory is absent, and that is the answer dotfiles wants -- distinct from
  # the probe's, which is what tells "not there" apart from "down".
  list)
    exec ssh "${SSH_OPTIONS[@]}" "$SHELF_HOST" "ls -1 -- ${1:?a directory is required}"
    ;;
  upload)
    exec scp "${SSH_OPTIONS[@]}" -- "${1:?a local file is required}" "$SHELF_HOST:${2:?a directory is required}/"
    ;;
  download)
    exec scp "${SSH_OPTIONS[@]}" -- "$SHELF_HOST:${1:?a remote path is required}" "${2:?a local path is required}"
    ;;
  mkdir)
    exec ssh "${SSH_OPTIONS[@]}" "$SHELF_HOST" "mkdir -p -- ${1:?a directory is required}"
    ;;
  delete)
    exec ssh "${SSH_OPTIONS[@]}" "$SHELF_HOST" "rm -f -- ${1:?a remote path is required}"
    ;;
  *)
    echo "shelf-transport: unknown operation '$operation'" >&2
    exit 2
    ;;
esac
