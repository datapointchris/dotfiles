#!/usr/bin/env bash

detect_os() {
    case "$(uname -s)" in
        Darwin) echo "darwin" ;;
        Linux)  echo "linux" ;;
        *)      echo "unknown" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)     echo "amd64" ;;
        arm64|aarch64)    echo "arm64" ;;
        *)                uname -m ;;
    esac
}

detect_platform() {
    # Respect PLATFORM environment variable if already set (for testing)
    if [[ -n "${PLATFORM:-}" ]]; then
        echo "$PLATFORM"
        return 0
    fi

    local os
    os=$(detect_os)

    if [[ "$os" == "darwin" ]]; then
        echo "macos"
    elif [[ "$os" == "linux" ]]; then
        if grep -q "Microsoft\|WSL" /proc/version 2>/dev/null; then
            echo "wsl"
        elif [[ -f /etc/arch-release ]]; then
            echo "arch"
        else
            echo "linux"
        fi
    else
        echo "unknown"
    fi
}
