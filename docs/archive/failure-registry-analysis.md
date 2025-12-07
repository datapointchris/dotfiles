# Failure Registry System Analysis

**Date**: 2025-12-06
**Status**: Analysis Complete
**Author**: Claude Code

## Executive Summary

The dotfiles installation system has **two failure tracking mechanisms**:

1. **NEW SYSTEM** (Working): `FAILURES_LOG` + `output_failure_data()` + `run_installer.sh` wrapper
2. **OLD SYSTEM** (Dead Code): `DOTFILES_FAILURE_REGISTRY` + `report_failure()` function

The old system code exists in 14 installer files but **does not work** because:
- The `DOTFILES_FAILURE_REGISTRY` variable is never set
- The `report_failure()` function doesn't exist
- The conditional blocks are never executed

**HOWEVER**: These dead code blocks contain valuable **manual installation instructions** that help users in restricted network environments. We need to preserve this content while transitioning to the new system.

---

## How The NEW System Works (Current - Functional)

### 1. Initialization (install.sh)

```bash
# Line 94-95 in install.sh
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
export FAILURES_LOG
```

- Creates timestamped log file in `/tmp`
- Exported to all child processes
- Single append-only file for all failures

### 2. Wrapper Function (management/lib/run-installer.sh)

```bash
run_installer() {
  local script="$1"
  local tool_name="$2"

  # Capture stderr to parse structured failure data
  bash "$script" 2> >(tee "$stderr_file" >&2)

  # On failure, parse stderr for structured data
  failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2)
  failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2)
  # ... parse other fields ...

  # Append formatted failure to FAILURES_LOG
  cat >> "$FAILURES_LOG" << EOF
========================================
$failure_tool - Installation Failed
========================================
Download URL: $failure_url
Version: $failure_version
Reason: $failure_reason
Manual Installation Steps:
$failure_manual
---
EOF
}
```

**Key Points**:
- Runs each installer script
- Captures stderr to parse structured failure output
- Extracts `FAILURE_TOOL`, `FAILURE_URL`, `FAILURE_VERSION`, `FAILURE_REASON`, `FAILURE_MANUAL`
- Appends formatted failure info to `$FAILURES_LOG`
- Works with any script that outputs structured failure data to stderr

### 3. Structured Failure Output (management/common/lib/install-helpers.sh)

```bash
output_failure_data() {
  local tool_name="$1"
  local download_url="$2"
  local version="${3:-unknown}"
  local manual_steps="$4"
  local reason="${5:-Installation failed}"

  # Output to stderr in parseable format
  cat >&2 << EOF
FAILURE_TOOL='$tool_name'
FAILURE_URL='$download_url'
FAILURE_VERSION='$version'
FAILURE_REASON='$reason'
FAILURE_MANUAL<<'END_MANUAL'
$manual_steps
END_MANUAL
EOF
}
```

**Key Points**:
- NEW function (replaces old `report_failure()`)
- Outputs structured data to stderr (not a file)
- Uses shell variable format for easy parsing
- Heredoc for multi-line manual steps
- Wrapper (`run_installer.sh`) parses this and writes to log

### 4. Modern Installers Using NEW System

**Example: github-release-installer.sh library**

```bash
install_from_tarball() {
  if ! curl -fsSL "$download_url" -o "$temp_tarball"; then
    local manual_steps="1. Download in your browser (bypasses firewall):
   $download_url

2. After downloading, extract and install:
   tar -xzf ~/Downloads/${binary_name}.tar.gz
   mv ${binary_path_in_tarball} ~/.local/bin/
   chmod +x ~/.local/bin/${binary_name}

3. Verify installation:
   ${binary_name} --version"

    # Output structured failure data (Option B pattern)
    output_failure_data "$binary_name" "$download_url" "$version" "$manual_steps" "Download failed"
    log_error "Failed to download from $download_url"
    return 1
  fi
}
```

**Installers using this pattern correctly**:
- `lazygit.sh`, `yazi.sh`, `glow.sh`, `duf.sh`, `tflint.sh`, `fzf.sh`, `neovim.sh`
- All GitHub release installers that use the library
- Works perfectly with `run_installer.sh` wrapper

### 5. Summary Display (install.sh)

```bash
show_failures_summary() {
  if [[ ! -f "$FAILURES_LOG" ]]; then
    return 0
  fi

  # Count failures (each has a separator line)
  failure_count=$(grep -c "^---$" "$FAILURES_LOG" || echo 0)

  if [[ $failure_count -eq 0 ]]; then
    return 0
  fi

  log_warning "$failure_count installation(s) failed"
  cat "$FAILURES_LOG"
  echo "Full report saved to: $FAILURES_LOG"
}
```

**Key Points**:
- Reads single log file at end of installation
- Counts failures by counting `---` separators
- Displays full formatted report to user
- Shows file path for later reference

---

## How The OLD System SHOULD Work (Dead Code - Non-Functional)

### 1. Initialization (NEVER HAPPENS)

```bash
# This code DOES NOT EXIST in install.sh
DOTFILES_FAILURE_REGISTRY="/tmp/dotfiles-failures-$$/"
export DOTFILES_FAILURE_REGISTRY
mkdir -p "$DOTFILES_FAILURE_REGISTRY"
```

**Reality**: The variable is never set, so it's always empty.

### 2. Report Function (DOESN'T EXIST)

```bash
# This function DOES NOT EXIST anywhere in the codebase
report_failure() {
  local tool_name="$1"
  local download_url="$2"
  local version="$3"
  local manual_steps="$4"
  local reason="$5"

  local failure_file="$DOTFILES_FAILURE_REGISTRY/$(date +%s)-${tool_name}.txt"

  cat > "$failure_file" << EOF
TOOL=$tool_name
URL=$download_url
VERSION=$version
REASON=$reason
MANUAL_STEPS=$manual_steps
EOF
}
```

**Reality**: Function doesn't exist. Calls to it would fail if the conditional ever executed.

### 3. Dead Code Pattern in Installers

```bash
# Example from awscli.sh (lines 104-111)
if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
  manual_steps="The AWS CLI installer failed. Try manually:
   1. Download: $ZIP_URL
   2. Extract: unzip ~/Downloads/awscliv2.zip
   3. Install: ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin

Official docs: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  report_failure "aws" "$ZIP_URL" "latest" "$manual_steps" "AWS installer failed"
fi
```

**Why it's dead code**:
1. `${DOTFILES_FAILURE_REGISTRY:-}` is always empty (variable never set)
2. The `if` condition is always false
3. Even if it were true, `report_failure()` doesn't exist
4. **BUT**: The `manual_steps` string is valuable and should be preserved

---

## Files Containing Dead Code

### Custom Installers (3 files)

1. **awscli.sh** (3 blocks with manual steps)
   - Line 104-111: AWS installer failure
   - Line 135-147: Installation verification failure
   - Line 79-92: Download failure

2. **claude-code.sh** (2 blocks with manual steps)
   - Line 78-90: Installer failure
   - Line 101-116: Installation verification failure

3. **terraformer.sh** (2 blocks with manual steps)
   - Line 41-53: Download failure
   - Line 63-73: PATH verification failure

### Language Tools (3 files)

4. **cargo-tools.sh** (1 block)
   - Line 34-40: cargo-binstall failure

5. **go-tools.sh** (1 block)
   - Line 43-49: go install failure

6. **npm-install-globals.sh** (1 block)
   - Line 47-53: npm install failure

### Plugin Installers (3 files)

7. **tmux-plugins.sh** (2 blocks)
   - Line 26-35: TPM plugin installation failure
   - Line 41-47: TPM not found

8. **shell-plugins.sh** (1 block)
   - Line 47-54: git clone failure

9. **nvim-plugins.sh** (1 block)
   - Line 30-41: Lazy.nvim sync failure

### Other Installers (2 files)

10. **fonts.sh** (1 block)
    - Line 1126-1138: Font download failure (with retry logic)

11. **update.sh** (4 blocks in management/common/update.sh)
    - Line 64-70: UV tools update failure
    - Line 83-89: Cargo packages update failure
    - Line 114-118: Shell plugin git pull failure
    - Line 147-153: Tmux plugin update failure

**Total**: 14 files with 24 dead code blocks

---

## Why The Dead Code Is Valuable

Each dead code block contains **detailed manual installation instructions** like:

```bash
manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, extract and install:
   unzip ~/Downloads/awscliv2.zip
   ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin

3. Verify installation:
   aws --version

Official docs: https://docs.aws.amazon.com/..."
```

**Why this is important**:
- Helps users in corporate environments with firewall restrictions
- Provides step-by-step recovery instructions
- Includes official documentation links
- Shows exact commands to run manually

**What we must NOT do**:
- Remove the manual steps entirely
- Replace with generic "installation failed" messages
- Lose the troubleshooting information

---

## The Transition Strategy

### Goal

Preserve all manual installation instructions while removing dead code and transitioning to the new `FAILURES_LOG` + `output_failure_data()` system.

### Safe Transition Pattern

**BEFORE (Dead Code)**:
```bash
if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, extract and install:
   unzip ~/Downloads/tool.zip
   mv tool ~/.local/bin/

3. Verify installation:
   tool --version"
  report_failure "tool" "$DOWNLOAD_URL" "v1.0" "$manual_steps" "Download failed"
fi
log_warning "Tool installation failed (see summary)"
exit 1
```

**AFTER (New System)**:
```bash
manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, extract and install:
   unzip ~/Downloads/tool.zip
   mv tool ~/.local/bin/

3. Verify installation:
   tool --version"

output_failure_data "tool" "$DOWNLOAD_URL" "v1.0" "$manual_steps" "Download failed"
log_warning "Tool installation failed (see summary)"
exit 1
```

**Key Changes**:
1. ✅ Keep the `manual_steps` string (valuable content)
2. ❌ Remove the `if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]` conditional
3. ❌ Remove the `report_failure()` call (doesn't exist)
4. ✅ Add `output_failure_data()` call (exists, works with wrapper)
5. ✅ Keep existing error logging and exit codes

### Why This Works

1. **Manual steps preserved**: All troubleshooting info retained
2. **Wrapper compatible**: `run_installer.sh` already parses `output_failure_data()` output
3. **Log file integration**: Failures automatically appear in `$FAILURES_LOG`
4. **Summary display**: User sees formatted report at end via `show_failures_summary()`
5. **No behavior change**: Scripts still exit with code 1, wrapper still logs failure

---

## Implementation Plan

### Phase 1: Custom Installers (High Value)

These have the most detailed manual steps and are most likely to fail in restricted environments.

**Files**:
1. `awscli.sh` (3 blocks)
2. `claude-code.sh` (2 blocks)
3. `terraformer.sh` (2 blocks)

**Pattern**:
- Replace each `if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]` block
- Extract `manual_steps` variable outside conditional
- Call `output_failure_data()` instead of `report_failure()`
- Test that failures still appear in summary

### Phase 2: Language Tools (Medium Value)

**Files**:
1. `cargo-tools.sh` (1 block)
2. `go-tools.sh` (1 block)
3. `npm-install-globals.sh` (1 block)

**Same pattern as Phase 1**

### Phase 3: Plugin Installers (Medium Value)

**Files**:
1. `tmux-plugins.sh` (2 blocks)
2. `shell-plugins.sh` (1 block)
3. `nvim-plugins.sh` (1 block)

**Same pattern as Phase 1**

### Phase 4: Special Cases (Low Priority)

**Files**:
1. `fonts.sh` (1 block with retry logic)
2. `update.sh` (4 blocks in update script)

**Notes**:
- `fonts.sh` has special retry logic - need to test carefully
- `update.sh` is a different script (not run by `run_installer.sh` wrapper)
- May need different approach for update scripts

### Phase 5: Update Documentation

**Files to update**:
- Archive old failure registry docs (already done)
- Update any references to failure handling
- Add note about `output_failure_data()` pattern

---

## Testing Strategy

### Unit Tests

For each modified installer:

```bash
# Set up test environment
export FAILURES_LOG="/tmp/test-failures.txt"
rm -f "$FAILURES_LOG"

# Simulate failure condition
bash installer.sh 2>&1 | tee /tmp/test-output.txt

# Verify structured data in stderr
grep -q "FAILURE_TOOL='tool'" /tmp/test-output.txt
grep -q "FAILURE_MANUAL" /tmp/test-output.txt

# Verify manual steps preserved
grep -q "Download in your browser" /tmp/test-output.txt
```

### Integration Tests

Run through `run_installer.sh` wrapper:

```bash
export FAILURES_LOG="/tmp/test-failures.txt"
run_installer "path/to/installer.sh" "tool-name"

# Verify failure logged to file
grep -q "tool-name - Installation Failed" "$FAILURES_LOG"
grep -q "Manual Installation Steps:" "$FAILURES_LOG"
grep -q "Download in your browser" "$FAILURES_LOG"
```

### Full Installation Test

```bash
# Run full install.sh with mock failures
SKIP_FONTS=1 ./install.sh

# Verify summary shows failures
# Verify FAILURES_LOG contains all failures
# Verify manual steps are included
```

---

## Example Transformation

### Before: awscli.sh (lines 79-92)

```bash
log_info "Downloading AWS CLI..."
if ! curl -fsSL "$ZIP_URL" -o "$ZIP_FILE"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $ZIP_URL

2. After downloading, extract and install:
   unzip ~/Downloads/awscliv2.zip
   ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin

3. Verify installation:
   aws --version"
  report_failure "aws" "$ZIP_URL" "latest" "$manual_steps" "Download failed"
  log_warning "AWS CLI installation failed (see summary)"
  exit 1
fi
```

### After: awscli.sh (transformed)

```bash
log_info "Downloading AWS CLI..."
if ! curl -fsSL "$ZIP_URL" -o "$ZIP_FILE"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $ZIP_URL

2. After downloading, extract and install:
   unzip ~/Downloads/awscliv2.zip
   ./aws/install --install-dir ~/.local/aws-cli --bin-dir ~/.local/bin

3. Verify installation:
   aws --version"

  output_failure_data "aws" "$ZIP_URL" "latest" "$manual_steps" "Download failed"
  log_warning "AWS CLI installation failed (see summary)"
  exit 1
fi
```

**Changes**:
1. ❌ Removed: `if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then`
2. ❌ Removed: `report_failure` call
3. ✅ Added: `output_failure_data` call
4. ✅ Preserved: All manual steps exactly as-is
5. ✅ Preserved: Error logging and exit behavior

---

## Files That DON'T Need Changes

### Already Using New System

All GitHub release installers using `github-release-installer.sh` library:
- `lazygit.sh`
- `yazi.sh`
- `glow.sh`
- `duf.sh`
- `tflint.sh`
- `terrascan.sh`
- `trivy.sh`
- `zk.sh`
- `fzf.sh`
- `neovim.sh`

These call `install_from_tarball()` or `install_from_zip()` which already use `output_failure_data()`.

### Simple Scripts Without Failure Reporting

- `uv-tools.sh` - Just logs warnings, no structured failure reporting
- Most language manager installers - Exit early without detailed manual steps

---

## Benefits of This Transition

### For Users

1. **Same helpful manual steps** - No loss of troubleshooting information
2. **Better formatting** - Consistent failure report format
3. **Single log file** - All failures in one place with timestamp
4. **Clear summary** - Count of failures and formatted report

### For Maintainers

1. **No dead code** - Remove variables/functions that don't exist
2. **Single pattern** - All installers use same failure reporting mechanism
3. **Easier testing** - Simple pattern to verify
4. **Clear documentation** - One system to explain

### For The Codebase

1. **Consistency** - All installers follow same pattern
2. **Simpler** - File-based append instead of registry directory
3. **Tested** - Already working in modern installers
4. **Maintainable** - Clear separation: installers output data, wrapper writes log

---

## Risks and Mitigations

### Risk: Breaking Manual Steps

**Mitigation**:
- Keep all manual_steps strings exactly as-is
- Test that they appear in failures log
- Review each transformation carefully

### Risk: Changing Script Behavior

**Mitigation**:
- Keep all exit codes the same
- Keep all log messages the same
- Only change failure reporting mechanism
- Test with real failures

### Risk: Missing Edge Cases

**Mitigation**:
- Test each installer individually
- Test through wrapper
- Test full install.sh flow
- Review special cases (fonts.sh, update.sh) separately

---

## Next Steps

1. **Get user approval** on this analysis and approach
2. **Start with Phase 1** (custom installers) - highest value, most detailed manual steps
3. **Test thoroughly** after each file transformation
4. **Commit after each phase** - logical grouping for easier review
5. **Document the new pattern** - Update architecture docs
6. **Clean up old code** - Remove references to DOTFILES_FAILURE_REGISTRY from tests/docs

---

## Questions for User

Before proceeding with implementation:

1. **Approach validation**: Does this transition strategy make sense?
2. **Phasing**: Should we do all at once or phase-by-phase with separate commits?
3. **Testing**: What level of testing do you want before committing? (unit, integration, full)
4. **Special cases**: How should we handle `update.sh` (not run by wrapper)?
5. **Documentation**: Should we create a new doc explaining the failure reporting pattern?

---

## Conclusion

The failure reporting system has evolved from a registry-based approach to a simpler log-based approach. The dead code from the old system exists in 14 files but contains valuable manual installation instructions that must be preserved.

The transition is straightforward:
- Remove conditional checks for non-existent variable
- Remove calls to non-existent function
- Add calls to existing `output_failure_data()` function
- Preserve all manual steps content

The new system is already working in modern installers and provides better consistency and simpler maintenance.
