# Adding Failure Reporting to Installers

## Quick Start

Adding resilient failure handling to a new installer script involves four key steps:

1. Source install-helpers.sh
2. Initialize failure registry
3. Report failures before exit
4. Display summary at end

## Complete Example

Here's a complete installer template with failure reporting:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# Install Example Tool
# ================================================================

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}

# Source libraries
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

print_banner "Installing Example Tool"

# Initialize failure registry
init_failure_registry

TOOL_NAME="example-tool"
VERSION="v1.0.0"
DOWNLOAD_URL="https://github.com/example/tool/releases/download/${VERSION}/tool.tar.gz"
TEMP_FILE="/tmp/example-tool.tar.gz"

# Check if already installed
if command -v "$TOOL_NAME" >/dev/null 2>&1; then
  CURRENT_VERSION=$($TOOL_NAME --version 2>&1 | head -n1)
  log_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Download
log_info "Downloading $TOOL_NAME..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_FILE"; then
  # Report failure if registry exists
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, extract and install:
   tar -xzf ~/Downloads/tool.tar.gz
   mv tool ~/.local/bin/
   chmod +x ~/.local/bin/$TOOL_NAME

3. Verify installation:
   $TOOL_NAME --version"
    report_failure "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  fi
  log_warning "$TOOL_NAME installation failed (see summary)"
  display_failure_summary
  exit 1
fi

# Extract
log_info "Extracting..."
tar -xzf "$TEMP_FILE" -C /tmp

# Install
log_info "Installing to ~/.local/bin..."
mv "/tmp/tool" "$HOME/.local/bin/$TOOL_NAME"
chmod +x "$HOME/.local/bin/$TOOL_NAME"

# Cleanup
rm -f "$TEMP_FILE"

# Verify
if command -v "$TOOL_NAME" >/dev/null 2>&1; then
  INSTALLED_VERSION=$($TOOL_NAME --version 2>&1 | head -n1)
  log_success "$INSTALLED_VERSION"
else
  # Report verification failure
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="$TOOL_NAME installed but not found in PATH.

Check installation:
   ls -la ~/.local/bin/$TOOL_NAME

Ensure ~/.local/bin is in PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify:
   $TOOL_NAME --version"
    report_failure "$TOOL_NAME" "unknown" "$VERSION" "$manual_steps" "Installation verification failed"
  fi
  log_warning "$TOOL_NAME installation verification failed (see summary)"
  display_failure_summary
  exit 1
fi

# Display failure summary
display_failure_summary

print_banner_success "$TOOL_NAME installation complete"
```

## Step-by-Step Guide

### 1. Source install-helpers.sh

Add this after sourcing logging and formatting libraries:

```bash
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"
```

### 2. Initialize Failure Registry

Call once near the beginning (after banner):

```bash
init_failure_registry
```

**When to call**:

- Required if script will be run standalone
- Optional if only called from install.sh wrapper (wrapper initializes)
- Safe to call multiple times (idempotent)

### 3. Report Failures Before Exit

For each critical operation that might fail, wrap in error handling:

```bash
if ! critical_operation; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="..."
    report_failure "$TOOL" "$URL" "$VERSION" "$manual_steps" "$REASON"
  fi
  log_warning "$TOOL installation failed (see summary)"
  display_failure_summary
  exit 1
fi
```

**Critical operations to wrap**:

- Downloads (curl, wget)
- Extraction (tar, unzip)
- Installation steps
- Verification checks

### 4. Display Summary at End

Call before final success message:

```bash
display_failure_summary
print_banner_success "Installation complete"
```

This handles both success (no output) and failure (shows summary) cases.

## Writing Manual Steps

Manual steps should be **actionable and complete**. Follow this pattern:

```bash
manual_steps="1. [Action in browser/GUI to bypass restrictions]:
   [URL or specific instructions]

2. After [first step], [extraction/installation]:
   [Exact commands to run]
   [One command per line with proper paths]

3. Verify installation:
   [Command to verify it worked]"
```

### Examples

**GitHub release download**:

```bash
manual_steps="1. Download in your browser (bypasses firewall):
   https://github.com/user/repo/releases/download/v1.0/tool.tar.gz

2. After downloading, extract and install:
   tar -xzf ~/Downloads/tool.tar.gz
   mv tool ~/.local/bin/
   chmod +x ~/.local/bin/tool

3. Verify installation:
   tool --version"
```

**PATH verification failure**:

```bash
manual_steps="Tool installed but not found in PATH.

Check installation:
   ls -la ~/.local/bin/tool

Ensure ~/.local/bin is in PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Restart your shell or source profile:
   source ~/.zshrc

Verify:
   tool --version"
```

**Plugin installation (git clone)**:

```bash
manual_steps="Clone plugin manually with git:
   git clone $REPO_URL $PLUGIN_DIR

Or install to default location:
   cd ~/.config/zsh/plugins
   git clone $REPO_URL

Verify:
   ls -la $PLUGIN_DIR"
```

## Common Patterns

### Pattern 1: GitHub Release Installer (Using Library)

For standard GitHub releases, use the library:

```bash
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

# ... version detection ...

# Pass VERSION as 4th parameter (required for failure reporting)
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "path/in/tarball" "$VERSION"
```

The library handles failure reporting automatically.

### Pattern 2: Custom Download with curl

```bash
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_FILE"; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="1. Download in browser: $DOWNLOAD_URL
2. Extract: unzip ~/Downloads/file.zip
3. Install: mv binary ~/.local/bin/"
    report_failure "$TOOL" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  fi
  log_warning "$TOOL installation failed (see summary)"
  display_failure_summary
  exit 1
fi
```

### Pattern 3: Package Manager (npm, cargo, go)

For language package managers in loops:

```bash
for package in $PACKAGES; do
  if package_install_command "$package"; then
    log_success "$package installed"
  else
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      manual_steps="Install manually:
   package_install_command $package

Package info:
   [Package registry URL]"
      report_failure "$package" "$PACKAGE_URL" "latest" "$manual_steps" "Failed to install via package manager"
    fi
    log_warning "$package installation failed (see summary)"
  fi
done
```

**Important**: Don't exit in loops - continue to next package.

### Pattern 4: Plugin Installation (git clone)

```bash
if git clone "$REPO_URL" "$PLUGIN_DIR" --quiet; then
  log_success "$PLUGIN_NAME installed"
else
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="Clone manually:
   git clone $REPO_URL $PLUGIN_DIR"
    report_failure "$PLUGIN_NAME" "$REPO_URL" "latest" "$manual_steps" "Failed to clone repository"
  fi
  log_warning "$PLUGIN_NAME installation failed (see summary)"
fi
```

## Variable Scope: `manual_steps` Declaration

**Critical**: The `manual_steps` variable must be declared at the **correct scope**.

### ✅ Correct - Inside if block (not in function)

```bash
if ! curl -fsSL "$URL" -o "$FILE"; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="Download manually..."  # NO 'local' keyword
    report_failure "$TOOL" "$URL" "$VERSION" "$manual_steps" "Download failed"
  fi
fi
```

### ❌ Wrong - Using 'local' in if block

```bash
if ! curl -fsSL "$URL" -o "$FILE"; then
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    local manual_steps="..."  # ERROR: 'local' only valid in functions
    report_failure "$TOOL" "$URL" "$VERSION" "$manual_steps" "Download failed"
  fi
fi
```

### ✅ Correct - In function

```bash
install_tool() {
  local manual_steps="Download manually..."  # OK: inside function
  report_failure "$TOOL" "$URL" "$VERSION" "$manual_steps" "Failed"
}
```

**Rule**: Use `local` only inside functions. If you're in an if block at script level, omit `local`.

## Error Messages

### Generic Messages (Recommended)

Use generic messages that don't assume root cause:

- ✅ "Download failed"
- ✅ "Installation verification failed"
- ✅ "Failed to install via package manager"
- ✅ "Git clone failed"

### Avoid Assumptions

Don't assume why something failed:

- ❌ "Firewall blocked download"
- ❌ "Corporate proxy authentication required"
- ❌ "Network timeout"

**Why?** Failures have many causes. Let users diagnose based on manual steps.

## Testing Your Installer

### Test Standalone Execution

Your installer should work when run directly:

```bash
bash management/common/install/your-installer.sh
```

If failures occur, verify:

- Failure is reported correctly
- Manual steps are clear and complete
- Summary displays at end

### Test with Wrapper

Test through install.sh wrapper:

```bash
# Simulate failure by temporarily modifying installer
./install.sh
```

Verify:

- Wrapper reports failure
- Installation continues to next phase
- Summary includes your tool

### Test with ShellCheck

All installers must pass ShellCheck:

```bash
shellcheck management/common/install/your-installer.sh
```

Common issues:

- SC2168: Don't use `local` in if blocks
- SC2046: Quote command substitutions
- SC2086: Quote variables in commands

## Integration with install.sh

### Adding to install.sh Wrapper

Add your installer to the appropriate phase in `install.sh`:

```bash
# Phase X: Your Category
print_section "Installing Your Tool Category"
run_phase_installer "$common_installers/your-installer.sh" "your-tool"
```

The wrapper will:

- Initialize failure registry (if not already done)
- Catch your exit 1 and continue
- Check if you reported the failure
- Add generic entry if not
- Display summary at end

### Wrapper Contract

Your installer should:

1. Exit 0 on success
2. Call `report_failure()` before exiting with code 1
3. Call `display_failure_summary()` before exit
4. Work standalone (source install-helpers.sh, init registry)

The wrapper will:

1. Call your script with `bash script.sh`
2. Check exit code
3. Verify if failure was reported
4. Continue to next installer
5. Display final summary

## Checklist for New Installers

Before submitting, verify:

- [ ] Sources install-helpers.sh
- [ ] Calls init_failure_registry
- [ ] Wraps critical operations with error handling
- [ ] Reports failures before exit with report_failure()
- [ ] Calls display_failure_summary before exit
- [ ] Provides complete, actionable manual steps
- [ ] Uses generic error messages (no assumptions)
- [ ] Passes ShellCheck with no errors
- [ ] Works standalone (not just from install.sh)
- [ ] Added to install.sh in appropriate phase
- [ ] Tested with simulated failures

## Examples in Codebase

Reference these well-documented examples:

**Simple GitHub release**:

- `management/common/install/github-releases/lazygit.sh`

**Custom implementation**:

- `management/common/install/github-releases/yazi.sh`
- `management/common/install/custom-installers/awscli.sh`

**Package managers**:

- `management/common/install/language-tools/npm-install-globals.sh`
- `management/common/install/language-tools/cargo-tools.sh`

**Plugins**:

- `management/common/install/plugins/shell-plugins.sh`

## Getting Help

If you're unsure about any aspect:

1. Review existing installer scripts in the same category
2. Check the [Resilient Installation Architecture](../architecture/resilient-installation.md)
3. Run the test suite: `shellspec tests/unit/ && bash tests/integration/test_install_wrapper.sh`
4. Ask questions in GitHub discussions

## Related Documentation

- [Resilient Installation Architecture](../architecture/resilient-installation.md) - System overview
- [Error Handling](../architecture/error-handling.md) - General error handling patterns
- [GitHub Release Installer](../architecture/github-release-installer.md) - Using the library
- [Shell Libraries](../architecture/shell-libraries.md) - Logging and formatting
