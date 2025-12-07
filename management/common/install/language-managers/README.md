# Language Manager Installers

## Pattern

This directory contains installers for language version managers (uv, nvm, rustup, etc.). These tools manage multiple versions of programming languages and their associated toolchains.

**Key characteristics**:

- Each installer has unique installation method (curl install script, git clone, download binary)
- Install to language-specific directories (`~/.cargo`, `~/.config/nvm`, etc.)
- Modify PATH or require sourcing environment files
- One-time setup (not upgraded through these scripts)

## When to Use

Add a new installer to this directory when:

- Tool is a version manager for a programming language (pyenv, rbenv, goenv, etc.)
- Tool manages multiple versions of a language runtime
- Installation is one-time setup (not regular updates)
- Tool provides its own update mechanism

## Libraries Used

All scripts in this directory source:

```bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"  # For error reporting
```

## Standard Pattern

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_banner "Installing ToolName"

# Check if already installed
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v toolname >/dev/null 2>&1; then
  log_success "toolname already installed: $(toolname --version)"
  exit 0
fi

log_info "Installing toolname..."

# Installation method (unique per tool)
if ! installation_command; then
  manual_steps="Manual installation instructions..."
  output_failure_data "toolname" "https://install-url" "latest" "$manual_steps" "Installation failed"
  log_error "toolname installation failed"
  exit 1
fi

# Verify installation
if command -v toolname >/dev/null 2>&1; then
  log_success "toolname installed: $(toolname --version)"
else
  manual_steps="Binary installed but not in PATH..."
  output_failure_data "toolname" "https://install-url" "latest" "$manual_steps" "Not found in PATH"
  log_error "toolname not found in PATH"
  exit 1
fi
```

## Installation Methods by Tool

### curl | sh pattern (uv, rustup)

```bash
# uv.sh
XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH for current session
export PATH="$HOME/.local/bin:$PATH"
```

### Git clone pattern (nvm)

```bash
# nvm.sh
export NVM_DIR="${NVM_DIR:-$HOME/.config/nvm}"

if [[ ! -d "$NVM_DIR" ]]; then
  git clone https://github.com/nvm-sh/nvm.git "$NVM_DIR"
  cd "$NVM_DIR" && git checkout "$(git describe --abbrev=0 --tags --match "v[0-9]*" "$(git rev-list --tags --max-count=1)")"
fi
```

### Binary download pattern (go, tenv)

```bash
# Similar to github-release installers but language-specific
VERSION=$(get_latest_version "repo/name")
curl -LO "https://download-url/${VERSION}/archive.tar.gz"
tar -xzf archive.tar.gz -C ~/.local/
```

## Adding a New Tool

1. **Identify the installation method**
   - Check tool's official installation docs
   - Determine if it uses curl|sh, git clone, binary download, or other

2. **Create new script** named `toolname.sh`

3. **Implement idempotency check**:

   ```bash
   if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v toolname >/dev/null 2>&1; then
     log_success "toolname already installed: $(toolname --version)"
     exit 0
   fi
   ```

4. **Add installation logic** (unique per tool)

5. **Add error handling**:

   ```bash
   if ! installation_command; then
     manual_steps="1. Visit https://tool-website/install
   2. Follow platform-specific instructions
   3. Verify: toolname --version"
     output_failure_data "toolname" "https://install-url" "latest" "$manual_steps" "Installation failed"
     log_error "Installation failed"
     exit 1
   fi
   ```

6. **Verify installation**:

   ```bash
   if command -v toolname >/dev/null 2>&1; then
     log_success "installed: $(toolname --version)"
   else
     # Report PATH issue
     output_failure_data ...
     exit 1
   fi
   ```

7. **Document any environment setup** needed (in comments)

8. **Test the installer**:

   ```bash
   # Test installation
   bash management/common/install/language-managers/toolname.sh

   # Verify binary
   which toolname
   toolname --version

   # Test idempotency
   bash management/common/install/language-managers/toolname.sh
   ```

## Examples

### curl | sh installer (uv.sh)

```bash
log_info "Installing uv Python package manager..."

if ! XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/install.sh | sh; then
  manual_steps="1. Visit: https://docs.astral.sh/uv/getting-started/installation/
2. Run installer: curl -LsSf https://astral.sh/uv/install.sh | sh
3. Add to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\"
4. Verify: uv --version"
  output_failure_data "uv" "https://astral.sh/uv/install.sh" "latest" "$manual_steps" "curl install script failed"
  log_error "uv installation failed"
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"
log_success "uv installed: $(uv --version)"
```

### Git clone installer (nvm.sh)

```bash
export NVM_DIR="${NVM_DIR:-$HOME/.config/nvm}"

if [[ ! -d "$NVM_DIR" ]]; then
  log_info "Cloning nvm repository..."
  if ! git clone https://github.com/nvm-sh/nvm.git "$NVM_DIR"; then
    manual_steps="1. Clone nvm: git clone https://github.com/nvm-sh/nvm.git ~/.config/nvm
2. Checkout latest: cd ~/.config/nvm && git checkout \$(git describe --abbrev=0 --tags)
3. Source nvm: source ~/.config/nvm/nvm.sh
4. Verify: nvm --version"
    output_failure_data "nvm" "https://github.com/nvm-sh/nvm" "latest" "$manual_steps" "git clone failed"
    log_error "nvm installation failed"
    exit 1
  fi

  cd "$NVM_DIR" && git checkout "$(git describe --abbrev=0 --tags --match "v[0-9]*" "$(git rev-list --tags --max-count=1)")"
fi

source "$NVM_DIR/nvm.sh"
log_success "nvm installed: $(nvm --version)"
```

## Error Handling

Language managers require careful error handling because:

- Installation methods vary widely
- Network failures are common (curl, git clone)
- PATH setup may not work immediately
- Some require shell restart to take effect

Always wrap critical operations with error checks and provide helpful manual installation steps.

## Important Notes

1. **No set -e**: Scripts use `set -uo pipefail` (not `-e`) to allow explicit error handling with `output_failure_data()`

2. **PATH modifications**: Some tools (uv, rust) try to modify shell configs - prevent with flags (UV_NO_MODIFY_PATH, --no-modify-path)

3. **Environment sourcing**: Some installers need to source environment files to verify installation (nvm, rust)

4. **TERM variable**: Export `TERM=${TERM:-xterm}` to prevent interactive prompts

5. **Idempotency**: Always check if tool exists before installing (use `FORCE_INSTALL` env var to override)

## Common Issues

**Issue**: curl | sh fails silently

- **Solution**: Check exit code and call `output_failure_data()` on failure

**Issue**: Tool installed but not in PATH

- **Solution**: Export PATH in script, document in error message

**Issue**: Installation requires restart

- **Solution**: Document in log message, provide instructions in error data

**Issue**: Network timeout on git clone

- **Solution**: Provide manual clone instructions with specific tag
