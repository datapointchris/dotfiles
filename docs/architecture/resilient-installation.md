# Resilient Installation System

## Overview

The dotfiles installation system is designed to handle failures gracefully in restricted network environments (corporate firewalls, VPNs, air-gapped networks). Instead of crashing on the first download failure, the system continues installation and provides a comprehensive failure report with manual remediation steps at the end.

This architecture solves the critical problem: **first failure crashes entire install.sh causing broken partial installation instead of a mostly-working system with a few missing packages**.

## Design Principles

### Fail-Fast Child Scripts, Resilient Wrapper

- **Individual installers** maintain `set -euo pipefail` and use `exit 1` on failures
- **Wrapper scripts** (install.sh, update.sh) catch failures and continue
- This separation of concerns keeps scripts simple and testable

### Backwards Compatibility

- All scripts work standalone without the failure registry
- Registry is optional - scripts check `${DOTFILES_FAILURE_REGISTRY:-}` before reporting
- No breaking changes to existing installer contracts

### User-Friendly Reporting

- Homebrew-style summary at the end of installation
- Detailed manual installation steps for each failure
- Full report saved to `/tmp/dotfiles-installation-failures-*.txt`
- Generic error messages (avoid assumptions about root cause)

## Architecture Components

### 1. Failure Registry

**Location**: `/tmp/dotfiles-failures-$$/`

Temporary directory created per installation session to track all failures.

**File Format**: Source-able bash format for easy parsing

```bash
TOOL='yazi'
URL='https://github.com/sxyazi/yazi/releases/download/v0.2.4/yazi-x86_64-unknown-linux-gnu.zip'
VERSION='v0.2.4'
REASON='Download failed'
MANUAL_STEPS=$'1. Download in browser: https://...\n2. Extract and install...'
```

**Why source-able format?**

- Simple to parse with bash `source` command
- No external dependencies (jq, yq)
- Variables automatically available in current shell

### 2. Core Functions

Located in `management/common/lib/install-helpers.sh`:

#### `init_failure_registry()`

Initialize the failure registry for the current session.

```bash
init_failure_registry
# Creates: /tmp/dotfiles-failures-<PID>/
# Sets: DOTFILES_FAILURE_REGISTRY environment variable
```

**When to call**: Once at the beginning of install.sh or update.sh

#### `report_failure()`

Report a failed installation with context.

```bash
report_failure "$tool_name" "$download_url" "$version" "$manual_steps" "$error_reason"
```

**Parameters**:

- `tool_name`: Name of the tool (e.g., "yazi", "lazygit")
- `download_url`: URL that failed (or "unknown")
- `version`: Version attempted (or "latest", "unknown")
- `manual_steps`: Multi-line instructions for manual installation
- `error_reason`: Brief reason (e.g., "Download failed", "Installation verification failed")

**File naming**: `<timestamp>-<tool_name>.txt` for uniqueness and ordering

#### `display_failure_summary()`

Display formatted summary of all failures at end of installation.

```bash
display_failure_summary
```

**Output**:

- Console summary with all failures
- Manual installation steps for each
- Full report saved to `/tmp/dotfiles-installation-failures-<timestamp>.txt`

### 3. Wrapper Pattern (install.sh)

The main installation script wraps each installer with error catching:

```bash
run_phase_installer() {
    local script="$1"
    local tool_name="$2"

    if bash "$script"; then
        return 0
    else
        local exit_code=$?

        # Check if installer reported failure itself
        if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && \
           compgen -G "$DOTFILES_FAILURE_REGISTRY/*-${tool_name}.txt" > /dev/null 2>&1; then
            log_warning "$tool_name installation failed (details in summary)"
        else
            # Create generic failure report
            report_failure "$tool_name" "unknown" "unknown" \
                "Re-run: bash $script" \
                "Installation script exited with code $exit_code"
            log_warning "$tool_name installation failed (see summary)"
        fi

        return 1
    fi
}
```

**How it works**:

1. Run installer script
2. If fails, check if it reported failure itself
3. If not, create generic failure entry
4. Continue to next installer

### 4. Installer Pattern

Each installer sources install-helpers.sh and reports failures before exiting:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source libraries
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# Initialize registry (if running standalone)
init_failure_registry

# Download
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_FILE"; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="1. Download in browser: $DOWNLOAD_URL
2. Extract: tar -xzf ~/Downloads/tool.tar.gz
3. Install: mv tool ~/.local/bin/
4. Verify: tool --version"
    report_failure "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  fi
  log_warning "$TOOL_NAME installation failed (see summary)"
  display_failure_summary
  exit 1
fi

# ... rest of installation ...

# Display summary at end
display_failure_summary
```

## Implementation Coverage

### Phase 1: Core Infrastructure ✅

- Failure registry system
- Core functions (init, report, display)
- Wrapper in install.sh
- Comprehensive test suite (ShellSpec + bash integration tests)

### Phase 2: GitHub Release Installers ✅

**11 tools with enhanced library**:

- github-release-installer.sh library functions updated
- lazygit, glow, duf, fzf, zk, tflint, terrascan, trivy (via library)
- yazi, terraformer, neovim (custom implementations)

### Phase 3: Fonts Installer ✅

**22 font families** with resilient download:

- Wrapper function for each font download
- Continues downloading remaining fonts if one fails
- Groups font failures in summary

### Phase 4: Language Tools & Plugins ✅

**6 installer scripts**:

- cargo-tools.sh - Rust package installation
- npm-install-globals.sh - Node.js global packages
- go-tools.sh - Go tool installation
- shell-plugins.sh - ZSH plugins via git clone
- tmux-plugins.sh - TPM plugin installation
- nvim-plugins.sh - Lazy.nvim plugin sync

### Phase 5: Custom Installers ✅

**4 custom installers**:

- terraform-ls.sh - HashiCorp language server
- awscli.sh - AWS CLI official installer
- claude-code.sh - Claude Code official installer
- shellspec.sh - BDD testing framework

### Phase 6: Update Scripts ✅

**Update workflow resilience**:

- update.sh - Main wrapper with failure handling
- common/update.sh - Individual command error handling
- verify-installed-packages.sh - References installation failure reports

## Testing

### Unit Tests (ShellSpec)

**7 examples** testing core functionality:

```bash
shellspec tests/unit/
```

Tests:

- `init_failure_registry()` creates registry
- `report_failure()` writes files correctly
- Source-able format validation
- `display_failure_summary()` output formatting

### Integration Tests (Bash)

**10 assertions** testing wrapper behavior:

```bash
bash tests/integration/test_install_wrapper.sh
```

Tests:

- Wrapper handles successful installation
- Wrapper reports unreported failures
- Wrapper accepts self-reported failures
- Installation continues after failures
- Summary displays all failures

## Usage Examples

### Running Installation

Normal installation (with automatic failure handling):

```bash
./install.sh
```

If failures occur, you'll see:

```bash
════════════════════════════════════════════════════════════════
Installation Summary
════════════════════════════════════════════════════════════════

[WARNING] ▲ Some installations failed
[INFO] This is common in restricted network environments

────────────────────────────────────────────────────────────────
yazi - Manual Installation Required
────────────────────────────────────────────────────────────────
  Reason: Download failed
  Download: https://github.com/sxyazi/yazi/releases/download/v0.2.4/yazi.zip
  Version: v0.2.4

  Manual Steps:
    1. Download in browser: https://github.com/sxyazi/yazi/...
    2. Extract: unzip ~/Downloads/yazi.zip
    3. Install: mv yazi ~/.local/bin/
    4. Verify: yazi --version

════════════════════════════════════════════════════════════════
Full report saved to: /tmp/dotfiles-installation-failures-20250103-143022.txt
════════════════════════════════════════════════════════════════
```

### Verification After Installation

Run verification script in a fresh shell:

```bash
bash management/tests/verify-installed-packages.sh
```

If there are failures and a recent installation report exists:

```bash
[INFO] Installation failure report found: /tmp/dotfiles-installation-failures-20250103-143022.txt
[INFO] This may explain some missing tools - see the report for manual installation steps
```

### Updating Packages

Updates now continue even if individual packages fail:

```bash
./update.sh
```

Same failure reporting mechanism applies.

## Design Decisions

### Why /tmp instead of $HOME?

User explicitly requested no extra files in home directory. Failure reports are temporary and only relevant during/after installation.

### Why source-able format?

- **Simplicity**: No external parsers needed (jq, yq)
- **Performance**: Fast to read and parse
- **Compatibility**: Works in any bash environment
- **Maintenance**: Easy to debug - just cat the file

### Why not modify individual scripts to remove set -e?

**Separation of concerns**:

- Installers stay simple - fail fast on errors
- Wrapper handles orchestration and resilience
- Easier to test - scripts have clear contracts
- No mixing of concerns in installer logic

### Why generic error messages?

Corporate networks fail for many reasons:

- Firewalls blocking GitHub
- Proxy authentication required
- DNS resolution issues
- SSL certificate problems
- Bandwidth throttling

We can't know the root cause, so we provide generic guidance ("Download failed") instead of assuming ("Firewall blocked download").

## Troubleshooting

### Installation succeeds but tool missing

Check the failure report:

```bash
cat /tmp/dotfiles-installation-failures-*.txt
```

Follow manual installation steps for the missing tool.

### Want to re-run just failed installers

Each failure report includes the exact command:

```bash
bash management/common/install/github-releases/yazi.sh
```

### Verification shows failures but no report

The report is only created during installation/update. If you're running verification later, the report may have been cleaned up (system reboot, /tmp cleanup).

Re-run installation to regenerate the report:

```bash
./install.sh
```

## Future Enhancements

Potential improvements for consideration:

1. **Persistent failure tracking**: Option to save reports to `~/.cache/dotfiles/` for long-term reference
2. **Retry mechanism**: Automatic retry with exponential backoff for network failures
3. **Alternative download sources**: Fallback to mirrors when primary source fails
4. **Failure analytics**: Track common failure patterns across installations
5. **Interactive mode**: Prompt user to manually fix failures during installation

## Related Documentation

- [Error Handling](error-handling.md) - General error handling patterns
- [Shell Libraries](shell-libraries.md) - Logging and formatting libraries
- [GitHub Release Installer](github-release-installer.md) - GitHub release installer library
- [Package Management](package-management.md) - Overall package management strategy
