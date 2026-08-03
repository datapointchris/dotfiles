#!/usr/bin/env bash
# Test fixture: Unknown variable (should be skipped gracefully)
# shellcheck source=/dev/null
source "$UNKNOWN_VARIABLE/file.sh"
