#!/usr/bin/env bash
# Wrapper script for toolbox Go binary
# This allows the symlinks system to handle it like other scripts

# Resolve the real path of this script (follow symlinks)
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}" 2>/dev/null)"
SCRIPT_DIR="$(dirname "$REAL_SCRIPT")"

exec "$SCRIPT_DIR/toolbox/toolbox" "$@"
