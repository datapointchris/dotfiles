# Resilient Installation Failure Handling Plan

**Status**: Planning
**Created**: 2025-12-03
**Priority**: High
**Scope**: install.sh, update.sh, all installer scripts, verification scripts

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current State Analysis](#current-state-analysis)
3. [Requirements](#requirements)
4. [Solution Architecture](#solution-architecture)
5. [Detailed Design](#detailed-design)
6. [Implementation Plan](#implementation-plan)
7. [Testing Strategy](#testing-strategy)
8. [References](#references)

---

## Problem Statement

### The Critical Issue

On WSL systems in corporate environments, GitHub downloads are frequently blocked by firewalls. Currently:

1. **First failure crashes everything**: When yazi download fails in Phase 5, the entire install.sh exits due to `set -euo pipefail`
2. **Partial installation is broken**: User is left with an incomplete environment where nothing after the failure point was installed
3. **Manual instructions are lost**: `print_manual_install()` output scrolls away in terminal
4. **No recovery path**: User must manually track what failed and what succeeded

### Impact

- **WSL corporate users** cannot complete dotfiles installation
- **Manual workarounds** require extensive knowledge of which tools failed
- **No visibility** into what succeeded vs failed until after the fact
- **Broken installation state** is worse than clean failure

### User's Request

> "The first failure (yazi in this case) crashes the entire install script and then everything after that does not complete causing a broken installation instead of just a few missing packages"

Need:
- Continue installation despite individual failures
- Collect all failure information during installation
- Display comprehensive summary at end (Homebrew-style)
- Provide manual installation instructions for each failed package
- Apply to ALL download scenarios: GitHub releases, fonts, plugins, language tools, etc.

---

## Current State Analysis

### Installation Script Architecture

**install.sh** (main entry point):
- Uses `set -euo pipefail` → exits on first error
- Calls 40+ individual installer scripts sequentially
- Organized in phases:
  - Phase 3: Coding Fonts (fonts.sh)
  - Phase 4: Go Toolchain (go.sh + go-tools.sh)
  - Phase 5: GitHub Release Tools (15 scripts: fzf, neovim, lazygit, yazi, glow, duf, tflint, terraformer, terrascan, trivy, zk)
  - Phase 5b: Custom Distribution Tools (awscli, claude-code, terraform-ls)
  - Phase 6: Rust/Cargo Tools (rust.sh + cargo tools)
  - Phase 7: Language Package Managers (nvm, uv, tenv + their tools)
  - Phase 8: Shell Configuration (shell-plugins)
  - Phase 9: Custom Go Applications (sess, toolbox)
  - Phase 10: Symlinking Dotfiles
  - Phase 11: Theme System (tinty)
  - Phase 12: Plugin Installation (tpm, tmux-plugins, nvim-plugins)

### Existing Error Handling Infrastructure

**Good Foundation Already Exists:**

1. **program-helpers.sh** (management/common/lib/):
   - `print_manual_install()` - displays manual installation instructions
   - `download_file()` - handles downloads with error checking
   - `get_latest_github_release()` - fetches version info from GitHub API
   - Already used by: neovim.sh, go.sh, awscli.sh

2. **github-release-installer.sh** (management/common/lib/):
   - `get_platform_arch()` - platform detection
   - `get_latest_version()` - GitHub API calls
   - `should_skip_install()` - idempotency checking
   - `install_from_tarball()` - standard installation pattern
   - `install_from_zip()` - zip installation pattern
   - Uses `log_fatal()` which exits immediately

3. **Shell Libraries** (platforms/common/.local/shell/):
   - `logging.sh` - structured logging with [LEVEL] prefixes
   - `formatting.sh` - visual terminal output
   - `error-handling.sh` - traps, cleanup, retry logic

### Current Failure Behavior

**When download fails:**

```bash
# Example: yazi.sh
curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_ZIP"
if [[ $? -ne 0 ]]; then
  log_fatal "Failed to download from $DOWNLOAD_URL"  # Calls exit 1
fi
```

**Result**: Script exits, install.sh exits (due to set -e), everything stops.

**Some scripts already have fallback:**

```bash
# Example: neovim.sh, go.sh, awscli.sh
if ! download_file "$URL" "$OUTPUT" "neovim"; then
  print_manual_install "neovim" "$URL" "$VERSION" "pattern" "commands"
  exit 1  # Still exits!
fi
```

**Progress**: Manual instructions are printed, but then script exits anyway.

### Corporate Environment Context

From `docs/reference/support/corporate.md`:
- GitHub raw content blocked
- GitHub releases may be blocked
- npm/pip registries may require company mirrors
- Manual package download in browser often works (bypasses firewall)

---

## Requirements

### Functional Requirements

1. **Continue on Failure**: Installation must continue when individual tools fail to download/install
2. **Failure Collection**: Collect all failures with context (tool name, phase, reason, manual steps)
3. **Summary Display**: Show Homebrew-style summary at end with all failures and manual instructions
4. **Manual Instructions**: Provide copy-paste ready commands for manual installation
5. **Verification Robustness**: Verification scripts should report failures but not crash pipeline
6. **Universal Coverage**: Apply to ALL download scenarios:
   - GitHub releases (15+ tools)
   - Fonts (22 font families)
   - Custom installers (awscli, claude-code, terraform-ls)
   - Language tools (npm, cargo, go packages)
   - Plugins (tmux, nvim, shell plugins)

### Non-Functional Requirements

1. **Backwards Compatible**: Existing installer scripts should continue to work when run standalone
2. **Minimal Changes**: Prefer changes to install.sh wrapper over rewriting all installers
3. **Clear Ownership**: Failure handling logic should be centralized and easy to maintain
4. **Testable**: Must work in CI/CD and Docker test environments
5. **Idempotent**: Re-running install.sh should skip successful tools and retry failed ones

### Design Constraints

From CLAUDE.md and existing architecture:
- ✅ **Fail fast and loud** - Still fail when critical errors occur (bad arguments, missing dependencies)
- ✅ **Explicit over hidden** - Failure handling should be visible in install.sh
- ✅ **Straightforward over complex** - Simple file-based failure registry, not JSON/database
- ✅ **Solve root causes** - Don't hide errors, provide actionable solutions

---

## Solution Architecture

### High-Level Approach: Hybrid Wrapper + Enhanced Reporting

**Core Principle**: Individual installers remain simple and fail-fast, but install.sh catches failures and collects information.

### Architecture Diagram

```bash
┌─────────────────────────────────────────────────────────────┐
│ install.sh (Main Orchestrator)                              │
│                                                              │
│ 1. Initialize failure registry: /tmp/dotfiles-failures-$$/  │
│ 2. For each installer script:                               │
│    - Run with || true (allow failure)                       │
│    - Capture exit code                                      │
│    - Check for failure registry entries                     │
│ 3. Display summary at end                                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ calls (with error trapping)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Individual Installer Scripts (unchanged behavior)            │
│                                                              │
│ - Keep set -euo pipefail                                    │
│ - Keep exit 1 on errors                                     │
│ - Enhanced: report_failure() before exit                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ writes to
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Failure Registry: /tmp/dotfiles-failures-$$/                │
│                                                              │
│ - Simple directory with one file per failure                │
│ - Each file contains: tool, phase, error, manual steps      │
│ - Read by install.sh for summary                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**1. Wrapper-Based Error Handling (Install.sh Level)**

```bash
# In install.sh
run_installer() {
  local script="$1"
  local phase="$2"
  local tool_name="$3"

  if bash "$script" || true; then
    # Success - exit code 0
    return 0
  else
    # Failure - exit code non-zero
    # Check if failure was reported to registry
    if [[ -n "$(ls "$FAILURE_REGISTRY_DIR"/*-"$tool_name".txt 2>/dev/null)" ]]; then
      log_warning "$tool_name installation failed (see summary at end)"
    else
      # Unreported failure - create generic entry
      report_unreported_failure "$tool_name" "$phase"
    fi
    return 1
  fi
}
```

**2. Enhanced Failure Reporting (Installer Scripts)**

```bash
# In program-helpers.sh
report_failure() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-latest}"
  local manual_steps="$4"
  local error_reason="${5:-Download failed}"

  # Write to failure registry
  local registry_dir="${DOTFILES_FAILURE_REGISTRY:-/tmp/dotfiles-failures-$$}"
  mkdir -p "$registry_dir"

  local failure_file="$registry_dir/$(date +%s)-${tool_name}.txt"
  cat > "$failure_file" <<EOF
TOOL=$tool_name
URL=$download_url
VERSION=$version
REASON=$error_reason
MANUAL_STEPS<<STEPS_END
$manual_steps
STEPS_END
EOF

  # Also print to terminal (current behavior)
  print_manual_install "$tool_name" "$download_url" "$version" "" "$manual_steps"
}
```

**3. Summary Display (Homebrew-Style)**

```bash
# At end of install.sh
display_failure_summary() {
  local failure_files=("$FAILURE_REGISTRY_DIR"/*.txt)

  if [[ ${#failure_files[@]} -eq 0 ]]; then
    return 0
  fi

  print_header "Installation Summary" "yellow"
  echo ""
  log_warning "Some installations failed due to download restrictions"
  log_info "This is common in corporate environments with firewall restrictions"
  echo ""

  for file in "${failure_files[@]}"; do
    # Parse and display each failure
    source "$file"
    print_section "$TOOL - Manual Installation Required" "red"
    echo "  Reason: $REASON"
    echo "  Download: $URL"
    echo ""
    echo "  Manual Steps:"
    echo "$MANUAL_STEPS" | sed 's/^/    /'
    echo ""
  done

  # Save to persistent file for reference
  cat "${failure_files[@]}" > "$HOME/.dotfiles-installation-failures-$(date +%Y%m%d-%H%M%S).txt"
  echo "Full report saved to: ~/.dotfiles-installation-failures-*.txt"
}
```

---

## Detailed Design

### Component 1: Failure Registry

**Location**: `/tmp/dotfiles-failures-$$/`
**Format**: One text file per failure, parseable by bash source command

**File naming**: `<timestamp>-<tool_name>.txt`

**File format**:
```bash
TOOL=yazi
PHASE=5
URL=https://github.com/sxyazi/yazi/releases/download/v0.2.0/yazi-x86_64-unknown-linux-gnu.zip
VERSION=v0.2.0
REASON="Download failed - connection timeout or blocked by firewall"
MANUAL_STEPS<<STEPS_END
1. Download in your browser (bypasses firewall):
   https://github.com/sxyazi/yazi/releases/download/v0.2.0/yazi-x86_64-unknown-linux-gnu.zip

2. After downloading, run these commands:
   unzip ~/Downloads/yazi-x86_64-unknown-linux-gnu.zip -d /tmp/yazi-extract
   mv /tmp/yazi-extract/yazi-x86_64-unknown-linux-gnu/yazi ~/.local/bin/yazi
   mv /tmp/yazi-extract/yazi-x86_64-unknown-linux-gnu/ya ~/.local/bin/ya
   chmod +x ~/.local/bin/yazi ~/.local/bin/ya

3. Verify installation:
   yazi --version
STEPS_END
```

**Rationale**:
- Simple text format, easy to parse with bash `source`
- Timestamp prefix ensures unique filenames
- HEREDOC format preserves multiline manual steps
- No external dependencies (no jq, no python parsing)

### Component 2: Enhanced program-helpers.sh

**New Functions**:

```bash
# Initialize failure registry (called by install.sh)
init_failure_registry() {
  export DOTFILES_FAILURE_REGISTRY="/tmp/dotfiles-failures-$$"
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"

  # Cleanup on exit
  trap "rm -rf '$DOTFILES_FAILURE_REGISTRY'" EXIT
}

# Report failure to registry and terminal
report_failure() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-latest}"
  local manual_steps="$4"
  local error_reason="${5:-Download failed}"

  # Skip if no registry (running script standalone)
  if [[ -z "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    return 0
  fi

  local failure_file="$DOTFILES_FAILURE_REGISTRY/$(date +%s)-${tool_name}.txt"

  cat > "$failure_file" <<EOF
TOOL=$tool_name
URL=$download_url
VERSION=$version
REASON=$error_reason
MANUAL_STEPS<<STEPS_END
$manual_steps
STEPS_END
EOF
}

# Enhanced download_file with failure reporting
download_file_with_reporting() {
  local url="$1"
  local output="$2"
  local tool_name="$3"
  local manual_steps="${4:-}"

  log_info "Downloading from:" >&2
  echo "  $url" >&2

  if ! curl -# -L "$url" -o "$output"; then
    log_error "Download failed" >&2

    # Report to registry if available
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      report_failure "$tool_name" "$url" "latest" "$manual_steps" "Download failed - connection timeout or blocked by firewall"
    fi

    return 1
  fi

  # Verify download succeeded
  if [[ ! -f "$output" ]] || [[ ! -s "$output" ]]; then
    log_error "Downloaded file is missing or empty" >&2

    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      report_failure "$tool_name" "$url" "latest" "$manual_steps" "Downloaded file is empty or corrupted"
    fi

    return 1
  fi

  return 0
}
```

**Migration Strategy**:
- Keep existing `download_file()` for backwards compatibility
- Add new `download_file_with_reporting()` function
- Gradually migrate installers to use new function

### Component 3: Modified install.sh

**Changes**:

```bash
# At top of install.sh, after sourcing libraries
init_failure_registry

# New wrapper function
run_phase_installer() {
  local script="$1"
  local phase_number="$2"
  local tool_name="$3"

  # Run installer, allowing failure
  if bash "$script"; then
    return 0
  else
    local exit_code=$?

    # Check if failure was reported to registry
    if compgen -G "$DOTFILES_FAILURE_REGISTRY/*-${tool_name}.txt" > /dev/null; then
      # Failure reported - good
      log_warning "$tool_name installation failed (details in summary)"
    else
      # Unreported failure - create generic entry
      report_failure "$tool_name" "unknown" "unknown" \
        "Re-run: bash $script" \
        "Installation script exited with code $exit_code but did not report specific error"
    fi

    return 1
  fi
}

# Update phase installers to use wrapper
# Example for Phase 5:
print_header "Phase 5 - GitHub Release Tools" "cyan"
run_phase_installer "$github_releases/fzf.sh" 5 "fzf" || true
run_phase_installer "$github_releases/neovim.sh" 5 "neovim" || true
run_phase_installer "$github_releases/lazygit.sh" 5 "lazygit" || true
run_phase_installer "$github_releases/yazi.sh" 5 "yazi" || true
# ... etc for all installers

# At end of install.sh (before final success message)
display_failure_summary
```

**Critical**: Use `|| true` after each `run_phase_installer()` call to prevent `set -e` from exiting.

### Component 4: Installer Script Updates

**Pattern for GitHub Release Scripts**:

```bash
# Example: yazi.sh

# At top, check if failure registry is available
FAILURE_REPORTING_ENABLED="${DOTFILES_FAILURE_REGISTRY:+true}"

# In download section
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/yazi-${YAZI_TARGET}.zip"
TEMP_ZIP="/tmp/${BINARY_NAME}.zip"

log_info "Downloading yazi..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_ZIP"; then

  # Generate manual steps
  MANUAL_STEPS=$(cat <<'EOF'
1. Download in your browser (bypasses firewall):
   ${DOWNLOAD_URL}

2. After downloading, run these commands:
   unzip ~/Downloads/yazi-*.zip -d /tmp/yazi-extract
   mv /tmp/yazi-extract/yazi-*/yazi ~/.local/bin/yazi
   mv /tmp/yazi-extract/yazi-*/ya ~/.local/bin/ya
   chmod +x ~/.local/bin/yazi ~/.local/bin/ya

3. Verify installation:
   yazi --version
EOF
)

  # Report failure if registry available
  if [[ -n "$FAILURE_REPORTING_ENABLED" ]]; then
    report_failure "yazi" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" \
      "Download failed - connection timeout or blocked by firewall"
  fi

  # Print manual instructions (current behavior)
  print_manual_install "yazi" "$DOWNLOAD_URL" "$VERSION"

  log_fatal "Failed to download from $DOWNLOAD_URL" "${BASH_SOURCE[0]}" "$LINENO"
fi
```

**Pattern for Font Downloads**:

Fonts script is more complex (22 families). Strategy:

```bash
# In fonts.sh download functions
download_nerd_font() {
  local name="$1"
  local package="$2"

  if ! curl -fsSL "$DOWNLOAD_URL" -o "$TARBALL"; then
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      report_failure "font-$package" "$DOWNLOAD_URL" "latest" \
        "1. Download from: https://github.com/ryanoasis/nerd-fonts/releases/latest
2. Look for ${package}.tar.xz
3. Extract to ~/fonts/${name}/" \
        "Download failed for $name font"
    fi

    log_error "Failed to download $name - continuing with other fonts"
    return 1  # Return error but don't exit
  fi
}

# In download_all_families(), allow failures
download_all_families() {
  download_jetbrains || true
  download_cascadia || true
  download_meslo || true
  # ... etc, each with || true
}
```

**Pattern for Plugin Installation**:

```bash
# In nvim-plugins.sh, tmux-plugins.sh, shell-plugins.sh
# These use git clone which might fail

# Example: yazi plugins in yazi.sh
log_info "Installing flavors..."
if ! ya pkg add BennyOe/tokyo-night 2>&1; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    report_failure "yazi-theme-tokyo-night" \
      "https://github.com/BennyOe/tokyo-night" "latest" \
      "Manual install: ya pkg add BennyOe/tokyo-night" \
      "Git clone failed - GitHub may be blocked"
  fi
fi
# Continue with other plugins
```

### Component 5: Verification Script Updates

**Current Problem**: Verification scripts in `management/verify-*.sh` also use `set -e` and exit on first failure.

**Solution**: Similar pattern - collect verification failures, report at end.

```bash
# In management/verify-*.sh
VERIFICATION_FAILURES=()

verify_tool() {
  local tool="$1"
  local command_check="$2"

  if command -v "$tool" >/dev/null 2>&1; then
    log_success "$tool is installed"
    return 0
  else
    log_error "$tool is NOT installed"
    VERIFICATION_FAILURES+=("$tool")
    return 1
  fi
}

# At end
if [[ ${#VERIFICATION_FAILURES[@]} -gt 0 ]]; then
  print_header "Verification Failures" "yellow"
  echo "The following tools are not installed:"
  for tool in "${VERIFICATION_FAILURES[@]}"; do
    echo "  - $tool"
  done
  echo ""
  echo "Check ~/.dotfiles-installation-failures-*.txt for manual installation instructions"
  exit 1
else
  log_success "All tools verified successfully"
  exit 0
fi
```

### Component 6: Summary Display Format

**Homebrew-Style Output**:

```bash
════════════════════════════════════════════════════════════════
Installation Summary
════════════════════════════════════════════════════════════════

⚠️  Some installations failed due to download restrictions
ℹ️  This is common in corporate environments with firewall restrictions

────────────────────────────────────────────────────────────────
yazi - Manual Installation Required
────────────────────────────────────────────────────────────────
  Reason: Download failed - connection timeout or blocked by firewall
  Download: https://github.com/sxyazi/yazi/releases/download/v0.2.0/yazi-x86_64-unknown-linux-gnu.zip

  Manual Steps:
    1. Download in your browser (bypasses firewall):
       https://github.com/sxyazi/yazi/releases/download/v0.2.0/yazi-x86_64-unknown-linux-gnu.zip

    2. After downloading, run these commands:
       unzip ~/Downloads/yazi-*.zip -d /tmp/yazi-extract
       mv /tmp/yazi-extract/yazi-*/yazi ~/.local/bin/yazi
       mv /tmp/yazi-extract/yazi-*/ya ~/.local/bin/ya
       chmod +x ~/.local/bin/yazi ~/.local/bin/ya

    3. Verify installation:
       yazi --version

────────────────────────────────────────────────────────────────
glow - Manual Installation Required
────────────────────────────────────────────────────────────────
  Reason: Download failed - connection timeout or blocked by firewall
  Download: https://github.com/charmbracelet/glow/releases/download/v1.5.1/glow_Linux_x86_64.tar.gz

  Manual Steps:
    1. Download in your browser:
       https://github.com/charmbracelet/glow/releases/download/v1.5.1/glow_Linux_x86_64.tar.gz

    2. After downloading:
       tar -xzf ~/Downloads/glow_Linux_x86_64.tar.gz -C /tmp
       mv /tmp/glow ~/.local/bin/glow
       chmod +x ~/.local/bin/glow

    3. Verify:
       glow --version

════════════════════════════════════════════════════════════════
Full report saved to: ~/.dotfiles-installation-failures-20251203-143022.txt
════════════════════════════════════════════════════════════════
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Goal**: Establish failure collection mechanism and wrapper infrastructure.

**Tasks**:
1. ✅ Create `.planning/resilient-installation-failure-handling.md` (this document)
2. Update `management/common/lib/program-helpers.sh`:
   - Add `init_failure_registry()`
   - Add `report_failure()`
   - Add `download_file_with_reporting()`
3. Update `install.sh`:
   - Initialize failure registry
   - Add `run_phase_installer()` wrapper
   - Add `display_failure_summary()`
   - Add cleanup trap for registry
4. Test infrastructure:
   - Unit test failure registry with dummy failures
   - Test summary display formatting
   - Verify cleanup on exit

**Success Criteria**:
- Failure registry is created and cleaned up properly
- Summary display shows dummy failures correctly
- No changes to existing installer scripts yet

### Phase 2: GitHub Release Installers (Week 2)

**Goal**: Update all GitHub release installers to report failures.

**Installers to Update** (15 scripts):
1. fzf.sh
2. neovim.sh (already has print_manual_install)
3. lazygit.sh
4. yazi.sh
5. glow.sh
6. duf.sh
7. tflint.sh
8. terraformer.sh
9. terrascan.sh
10. trivy.sh
11. zk.sh
12. awscli.sh (already has print_manual_install)
13. claude-code.sh
14. terraform-ls.sh
15. go.sh (already has print_manual_install)

**Pattern for Each Script**:
```bash
# Replace direct curl calls with:
if ! curl -fsSL "$URL" -o "$OUTPUT"; then
  MANUAL_STEPS="..."
  report_failure "$TOOL" "$URL" "$VERSION" "$MANUAL_STEPS" "Download failed"
  log_fatal "Failed to download"  # Still exits
fi
```

**Update install.sh Phase 5 and 5b**:
```bash
run_phase_installer "$github_releases/fzf.sh" 5 "fzf" || true
run_phase_installer "$github_releases/neovim.sh" 5 "neovim" || true
# ... etc for all
```

**Testing**:
- Mock curl to fail for specific tools
- Verify failure is reported to registry
- Verify summary displays correct information
- Verify installation continues to next tool

**Success Criteria**:
- All GitHub release installers report failures
- Installation continues when one tool fails
- Summary shows all failures at end

### Phase 3: Fonts Installer (Week 2)

**Goal**: Make fonts.sh resilient to individual font family download failures.

**Changes**:
1. Update each `download_*` function to return error instead of exit
2. Add failure reporting for each font family
3. Update `download_all_families()` to use `|| true`
4. Ensure at least one font family succeeds before continuing

**Special Handling**:
- Fonts have 22 families - many potential failures
- Group failures by font family in summary
- Provide single manual download link to nerd-fonts releases

**Testing**:
- Mock curl to fail for specific font families
- Verify other fonts continue downloading
- Verify summary groups font failures

**Success Criteria**:
- Font download failures don't crash installation
- Summary shows which fonts failed
- At least some fonts install successfully

### Phase 4: Language Tools and Plugins (Week 3)

**Goal**: Handle failures in language package managers and plugin installations.

**Categories**:
1. **Language Managers**:
   - nvm.sh
   - rust.sh
   - uv.sh
   - tenv.sh

2. **Language Tools**:
   - cargo-tools.sh (uses cargo binstall)
   - npm-install-globals.sh (uses npm)
   - go-tools.sh (uses go install)
   - uv-tools.sh (uses uv tool install)

3. **Plugins**:
   - shell-plugins.sh (git clones)
   - tpm.sh (git clone)
   - tmux-plugins.sh (tmux plugin manager)
   - nvim-plugins.sh (lazy.nvim)

**Pattern**:
```bash
# For tools installed via package managers
while read -r package; do
  if ! cargo binstall -y "$package"; then
    report_failure "cargo-$package" \
      "https://crates.io/crates/$package" "latest" \
      "Manual: cargo install $package" \
      "Cargo binstall failed"
  fi
done
```

**Testing**:
- Mock failures for specific packages
- Verify installation continues
- Verify summary includes all failures

**Success Criteria**:
- Language tool failures don't crash installation
- Plugin failures don't crash installation
- Summary shows all failed packages/plugins

### Phase 5: Verification Scripts (Week 3)

**Goal**: Update verification scripts to collect and report failures without exiting.

**Scripts to Update**:
- `management/verify-install.sh`
- `management/test-install-macos.sh`
- `management/test-install-wsl.sh`
- `management/test-install-arch.sh`

**Changes**:
1. Collect verification failures in array
2. Continue checking all tools
3. Display summary at end
4. Reference installation failure report if it exists

**Testing**:
- Remove specific tools from PATH
- Verify verification continues
- Verify summary shows all missing tools

**Success Criteria**:
- Verification checks all tools before reporting
- Summary clearly indicates which tools are missing
- Links back to installation failure report

### Phase 6: Update Scripts and Documentation (Week 4)

**Goal**: Apply same patterns to update.sh and document the new system.

**Tasks**:
1. Update `management/common/update.sh` with failure handling
2. Update `management/macos/update.sh` with failure handling
3. Update `management/wsl/update.sh` with failure handling
4. Update `management/arch/update.sh` with failure handling
5. Document new failure handling in:
   - `docs/architecture/installation-failure-handling.md` (new)
   - `docs/reference/support/corporate.md` (update)
   - `docs/development/testing.md` (update)
   - `README.md` (mention resilient installation)

**Documentation Content**:
- How the failure system works
- How to add failure reporting to new installers
- How to interpret the failure summary
- Manual installation best practices
- Corporate environment workarounds

**Success Criteria**:
- Update scripts handle failures gracefully
- Documentation is comprehensive
- Contributors understand how to use system

---

## Testing Strategy

### Testing Framework: ShellSpec

**Why ShellSpec**:
- Full-featured BDD testing framework for bash/shell scripts
- Built-in mocking and stubbing capabilities
- Parallel test execution for fast feedback
- Code coverage support (with kcov)
- Active maintenance (updated 2025)

**Directory Structure**:
```bash
tests/
├── .shellspec                 # ShellSpec configuration
├── spec_helper.sh             # Common test helpers and setup
├── unit/                      # Unit tests for individual functions
│   ├── program_helpers_spec.sh
│   └── failure_registry_spec.sh
├── integration/               # Integration tests for script workflows
│   ├── install_wrapper_spec.sh
│   └── failure_summary_spec.sh
└── fixtures/                  # Test fixtures and mock data
    ├── mock_installers/
    └── sample_failures/
```

**ShellSpec Installation**: Added to custom-installers (same category as claude-code, awscli)

### Unit Testing with ShellSpec

**Test Coverage Areas**:

1. **Failure Registry Functions** (`tests/unit/failure_registry_spec.sh`):
   ```bash
   Describe 'init_failure_registry()'
     It 'creates registry directory with process ID'
       When call init_failure_registry
       The variable DOTFILES_FAILURE_REGISTRY should be defined
       The path "$DOTFILES_FAILURE_REGISTRY" should be directory
     End

     It 'sets up cleanup trap'
       # Test that registry is cleaned up on exit
     End
   End

   Describe 'report_failure()'
     Before 'init_failure_registry'

     It 'writes failure file with correct format'
       When call report_failure "yazi" "https://github.com/..." "v1.0" "manual steps" "Download failed"
       The file "$DOTFILES_FAILURE_REGISTRY/*-yazi.txt" should be exist
       The contents of file "$DOTFILES_FAILURE_REGISTRY/*-yazi.txt" should include "TOOL=yazi"
     End

     It 'skips reporting when registry not initialized'
       unset DOTFILES_FAILURE_REGISTRY
       When call report_failure "test" "url" "v1" "steps" "error"
       The status should be success
       The stderr should be blank
     End
   End
   ```

2. **Download Functions** (`tests/unit/download_helpers_spec.sh`):
   ```bash
   Describe 'download_file_with_reporting()'
     Mock curl
       return 1  # Simulate download failure
     End

     It 'reports failure when curl fails'
       When call download_file_with_reporting "https://..." "/tmp/test" "tool" "steps"
       The status should be failure
       The file "$DOTFILES_FAILURE_REGISTRY/*-tool.txt" should be exist
     End
   End
   ```

3. **Summary Display** (`tests/unit/failure_summary_spec.sh`):
   ```bash
   Describe 'display_failure_summary()'
     Before create_mock_failures

     It 'displays all failures in registry'
       When call display_failure_summary
       The output should include "Installation Summary"
       The output should include "yazi - Manual Installation Required"
       The output should include "glow - Manual Installation Required"
     End

     It 'saves report to home directory'
       When call display_failure_summary
       The file "$HOME/.dotfiles-installation-failures-*.txt" should be exist
     End
   End
   ```

### Integration Testing with ShellSpec

**Test Scenarios**:

1. **Single Installer Failure** (`tests/integration/single_failure_spec.sh`):
   ```bash
   Describe 'Installation with single tool failure'
     Mock curl
       case "$2" in
         *yazi*) return 1 ;;  # Fail yazi download
         *) %preserve ;;       # Pass through other downloads
       esac
     End

     It 'continues installation after yazi failure'
       When run install.sh
       The status should be success
       The output should include "Installation Summary"
       The output should include "yazi - Manual Installation Required"
     End
   End
   ```

2. **Multiple Failures** (`tests/integration/multiple_failures_spec.sh`):
   ```bash
   Describe 'Installation with multiple failures'
     # Mock curl to fail for yazi, glow, duf
     It 'reports all failures in order'
       The output should include "yazi"
       The output should include "glow"
       The output should include "duf"
     End
   End
   ```

3. **Font Failures** (`tests/integration/font_failures_spec.sh`):
   ```bash
   Describe 'Font installation with failures'
     # Mock failures for 5 font families
     It 'continues downloading other fonts'
       The output should include successful fonts
     End
   End
   ```

4. **Wrapper Behavior** (`tests/integration/install_wrapper_spec.sh`):
   ```bash
   Describe 'run_phase_installer() wrapper'
     It 'catches script exit and continues'
     It 'reports unreported failures'
     It 'allows successful scripts to proceed'
   End
   ```

### Smoke Testing

**Quick Sanity Checks** (`tests/smoke/`):

1. **Basic Functionality**:
   - Registry creation and cleanup
   - Failure reporting writes files
   - Summary displays without errors

2. **Backwards Compatibility**:
   - Standalone script execution works
   - Scripts run without DOTFILES_FAILURE_REGISTRY set

### End-to-End Testing

**Full Installation Scenarios** (`tests/e2e/`):

1. **Simulated Corporate Environment**:
   ```bash
   Describe 'Installation in restricted environment'
     # Block GitHub downloads for subset of tools
     It 'completes installation with partial failures'
     It 'displays comprehensive failure summary'
     It 'saves failure report to home directory'
   End
   ```

2. **Network Failure Simulation**:
   - Complete network failure (all downloads fail)
   - Partial network failure (specific hosts blocked)
   - Verify installation continues and reports correctly

### Regression Testing

**Existing Functionality** (`tests/regression/`):

1. **Standalone Script Execution**:
   ```bash
   Describe 'Individual installer scripts'
     It 'works without failure registry'
       unset DOTFILES_FAILURE_REGISTRY
       When run management/common/install/github-releases/yazi.sh
       The status should be defined
     End
   End
   ```

2. **Existing Test Scripts**:
   - Ensure `management/test-install-*.sh` still work
   - Verify no breaking changes to existing test infrastructure

### Running Tests

**Commands**:
```bash
# Run all tests
shellspec

# Run specific test file
shellspec tests/unit/program_helpers_spec.sh

# Run tests in parallel
shellspec --jobs 4

# Generate coverage report (requires kcov)
shellspec --kcov

# Run tests for specific phase
shellspec tests/unit/         # Unit tests only
shellspec tests/integration/  # Integration tests only
```

**CI/CD Integration**:
```bash
# In GitHub Actions or CI pipeline
- name: Run ShellSpec Tests
  run: |
    shellspec --format documentation
    shellspec --kcov --kcov-options="--coveralls-id=$COVERALLS_TOKEN"
```

---

## References

### Research Sources

1. [Bash Error Handling Best Practices](https://stackoverflow.com/questions/64786/error-handling-in-bash)
2. [Writing Robust Shell Scripts](https://www.davidpashley.com/articles/writing-robust-shell-scripts/)
3. [Bash Script Continue After Error](https://www.squash.io/ensuring-bash-scripts-continue-after-error-in-linux/)
4. [Error Handling in Bash Scripts](https://dev.to/unfor19/writing-bash-scripts-like-a-pro-part-2-error-handling-46ff)
5. [Homebrew Common Issues Documentation](https://docs.brew.sh/Common-Issues)

### Internal Documentation

1. `docs/reference/support/corporate.md` - Corporate environment workarounds
2. `docs/architecture/shell-libraries.md` - Shell library usage guide
3. `.planning/production-grade-management-enhancements.md` - Previous enhancement work
4. `.planning/installation-architecture-analysis.md` - Installation system architecture
5. `management/common/lib/program-helpers.sh` - Existing helper functions
6. `management/common/lib/github-release-installer.sh` - GitHub release patterns

### Example Implementations

- Homebrew's caveats system
- Ansible's failed task reporting
- Docker's build failure summaries

---

## Success Metrics

### Quantitative Metrics

1. **Resilience**: Installation should complete with N% of tools failed (target: 50%)
2. **Coverage**: 100% of download operations should report failures
3. **Clarity**: 100% of failures should include manual installation steps
4. **Performance**: Failure handling should add <5% to installation time

### Qualitative Metrics

1. **User Experience**: Users should feel installation is "mostly successful" even with some failures
2. **Actionability**: Users should be able to manually install failed tools without documentation
3. **Confidence**: Users should trust the summary report is accurate and complete
4. **Maintainability**: Contributors should easily understand how to add failure reporting

### Testing Metrics

1. **Test Coverage**: 100% of installer types should have failure test cases
2. **Regression Rate**: Zero regressions in existing functionality
3. **Documentation Quality**: All new patterns documented with examples

---

## Open Questions

1. **Persistent Failure Log**: Should we keep failure logs in `~/.dotfiles-failures/` permanently, or just during installation?
   - **Recommendation**: Save to `~/.dotfiles-installation-failures-<timestamp>.txt` for reference, don't accumulate

2. **Retry Logic**: Should we offer automatic retry for failed downloads?
   - **Recommendation**: No automatic retry - manual intervention ensures user understands the issue

3. **Dependency Failures**: If a dependency fails (e.g., Go), should we skip dependent tools (e.g., go-tools)?
   - **Recommendation**: Yes - add dependency checking to run_phase_installer()

4. **CI/CD Behavior**: Should failure handling be disabled in CI (fail fast)?
   - **Recommendation**: Add `DOTFILES_CI_MODE=true` environment variable to preserve fail-fast in CI

5. **Update.sh Behavior**: Should update.sh also collect failures or fail fast?
   - **Recommendation**: Yes, use same pattern - users may want to update subset of tools

---

## Next Steps

1. **Get User Approval**: Review this plan with user for feedback
2. **Start Phase 1**: Begin implementation with core infrastructure
3. **Iterative Testing**: Test each phase thoroughly before moving to next
4. **Documentation**: Document as we go, not at the end
5. **Real-World Testing**: Test on actual corporate WSL environment before considering complete

---

**Plan Author**: Claude (Assistant)
**Plan Reviewer**: Chris (User)
**Implementation Start**: TBD
**Estimated Completion**: 4 weeks
