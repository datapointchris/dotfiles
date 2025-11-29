#!/usr/bin/env bash
# ================================================================
# Platform Detection Utility
# ================================================================
# Provides detect_platform() function for use across all scripts
# Sources this file and call detect_platform to get: macos, wsl, arch, linux, unknown
# ================================================================

detect_platform() {
    local platform=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        platform="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if grep -q "Microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
            platform="wsl"
        elif [[ -f /etc/arch-release ]]; then
            platform="arch"
        elif [[ -f /etc/debian_version ]]; then
            platform="wsl"  # Assume Ubuntu/Debian is WSL for our use case
        else
            platform="linux"
        fi
    else
        platform="unknown"
    fi

    echo "$platform"
}
