# Orchestration Layer

Core infrastructure libraries sourced by `install.sh` to orchestrate the installation process.

## Files

### platform-detection.sh

Detects the current platform (macos, wsl, arch) and architecture.

**Functions:**

- `detect_platform()` - Returns: macos, wsl, or arch
- `detect_os()` - Returns: darwin or linux
- `detect_arch()` - Returns: amd64 or arm64

**Usage:**

```bash
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"

PLATFORM=$(detect_platform)  # macos, wsl, or arch
OS=$(detect_os)              # darwin or linux
ARCH=$(detect_arch)          # amd64 or arm64
```

### run-installer.sh

Wraps installer scripts to capture structured failure data and write to centralized failure log.

**Function:**

- `run_installer(script_path, tool_name)` - Execute installer, parse failures, log results

**How it works:**

1. Executes the installer script
2. Captures stderr to temporary file
3. Filters out `FAILURE_*` markers from user output (shows clean logs)
4. Parses structured failure data (see `common/lib/failure-logging.sh`)
5. Writes formatted failure information to `$FAILURES_LOG`

**Usage:**

```bash
source "$DOTFILES_DIR/management/orchestration/run-installer.sh"

# Run installer with error capture
run_installer "$common_install/github-releases/lazygit.sh" "lazygit"
```

**Failure Log Format:**

```bash
========================================
lazygit - Installation Failed
========================================
Script: /path/to/lazygit.sh
Exit Code: 1
Timestamp: 2025-12-07T12:30:00-08:00
Download URL: https://github.com/...
Version: v0.40.0
Reason: Download failed

Manual Installation Steps:
1. Download in your browser...
2. Extract and install...
---
```

## Architecture

These libraries form the **orchestration layer** between the main installer and individual installer scripts:

```text
install.sh (orchestrator)
    ↓ sources orchestration/
run_installer()
    ↓ executes
installer scripts (github-releases/*.sh, fonts/*.sh, etc.)
    ↓ sources common/lib/
failure-logging.sh, github-release-installer.sh, font-installer.sh
```

**Key distinction:**

- **orchestration/** - Sourced by install.sh (the orchestrator)
- **common/lib/** - Sourced by individual installer scripts

This separation reflects real architectural boundaries: orchestration controls HOW installers run, while libraries provide utilities FOR installer scripts.
