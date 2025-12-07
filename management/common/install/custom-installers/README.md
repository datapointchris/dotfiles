# Custom Installers

## Pattern

This directory contains installers for tools with unique installation methods that don't fit the standard patterns (GitHub releases, language managers, package managers, fonts, plugins).

**Key characteristics**:

- Each installer has completely custom logic
- Installation methods vary widely (official installers, special URLs, complex setup)
- May require platform-specific handling
- Often have dependencies or prerequisites

## When to Use

Add a new installer to this directory when:

- Tool doesn't fit any standard installation pattern
- Tool has official installer script (not curl | sh pattern)
- Installation requires multiple steps or special configuration
- Tool requires prerequisites or dependencies
- Download URL is not from GitHub releases

## Libraries Used

Scripts in this directory typically source:

```bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"  # If platform-specific
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"  # For error reporting
```

## Standard Pattern

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

print_banner "Installing ToolName"

# Check if already installed
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v toolname >/dev/null 2>&1; then
  log_success "toolname already installed: $(toolname --version)"
  exit 0
fi

log_info "Installing toolname..."

# Custom installation logic (unique per tool)
if ! custom_installation_steps; then
  manual_steps="Manual installation instructions..."
  output_failure_data "toolname" "https://install-url" "version" "$manual_steps" "Installation failed"
  log_error "Installation failed"
  exit 1
fi

# Verify installation
if command -v toolname >/dev/null 2>&1; then
  log_success "toolname installed: $(toolname --version)"
else
  manual_steps="Binary installed but not in PATH..."
  output_failure_data "toolname" "https://install-url" "version" "$manual_steps" "Not found in PATH"
  log_error "toolname not found in PATH"
  exit 1
fi
```

## Adding a New Tool

1. **Identify why it's custom**
   - Not a GitHub release?
   - Not a language package?
   - Official installer with complex logic?
   - Requires special configuration?

2. **Research installation method**
   - Check official documentation
   - Test manual installation
   - Identify prerequisites

3. **Create new script** named `toolname.sh`

4. **Implement custom logic**:
   - Download from special URL
   - Run official installer
   - Configure post-installation
   - Handle platform differences

5. **Add error handling**:
   - Wrap critical steps with error checks
   - Call `output_failure_data()` on failures
   - Provide detailed manual installation steps

6. **Document prerequisites** (in comments):

   ```bash
   # Prerequisites:
   # - Python 3.8+
   # - curl
   # - unzip
   ```

7. **Test thoroughly**:

   ```bash
   # Test installation
   bash management/common/install/custom-installers/toolname.sh

   # Verify
   which toolname
   toolname --version

   # Test idempotency
   bash management/common/install/custom-installers/toolname.sh
   ```

## Examples

### AWS CLI (awscli.sh)

Official AWS installer with platform-specific archives:

```bash
OS=$(detect_os)
ARCH=$(detect_arch)

if [[ "$OS" == "darwin" ]]; then
  AWSCLI_PKG="AWSCLIV2.pkg"
  AWSCLI_URL="https://awscli.amazonaws.com/AWSCLIV2.pkg"
else
  AWSCLI_PKG="awscli-exe-linux-${ARCH}.zip"
  AWSCLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}.zip"
fi

# Download
if ! curl -fsSL "$AWSCLI_URL" -o "/tmp/$AWSCLI_PKG"; then
  manual_steps="Download manually from: https://aws.amazon.com/cli/"
  output_failure_data "awscli" "$AWSCLI_URL" "latest" "$manual_steps" "Download failed"
  exit 1
fi

# Install (platform-specific)
if [[ "$OS" == "darwin" ]]; then
  sudo installer -pkg "/tmp/$AWSCLI_PKG" -target /
else
  unzip "/tmp/$AWSCLI_PKG"
  sudo ./aws/install
fi
```

### Terraform Language Server (terraform-ls.sh)

Uses HashiCorp releases (not GitHub):

```bash
REPO="hashicorp/terraform-ls"
VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')

OS=$(detect_os)
ARCH=$(detect_arch)

# HashiCorp uses different naming
[[ "$ARCH" == "amd64" ]] && HC_ARCH="amd64" || HC_ARCH="arm64"
[[ "$OS" == "darwin" ]] && HC_OS="darwin" || HC_OS="linux"

DOWNLOAD_URL="https://releases.hashicorp.com/terraform-ls/${VERSION}/terraform-ls_${VERSION}_${HC_OS}_${HC_ARCH}.zip"

# Download and install
temp_dir=$(mktemp -d)
if ! curl -fsSL "$DOWNLOAD_URL" -o "$temp_dir/terraform-ls.zip"; then
  manual_steps="1. Visit: https://releases.hashicorp.com/terraform-ls/
2. Download for your platform
3. Extract and move to ~/.local/bin/"
  output_failure_data "terraform-ls" "$DOWNLOAD_URL" "v$VERSION" "$manual_steps" "Download failed"
  exit 1
fi

unzip -q "$temp_dir/terraform-ls.zip" -d "$temp_dir"
mv "$temp_dir/terraform-ls" "$HOME/.local/bin/"
chmod +x "$HOME/.local/bin/terraform-ls"
```

### Claude Code (claude-code.sh)

Uses official npm installer:

```bash
# Requires Node.js/npm
if ! command -v npm >/dev/null 2>&1; then
  manual_steps="Claude Code requires Node.js/npm:
1. Install Node.js via nvm: bash management/common/install/language-managers/nvm.sh
2. Then install Claude Code: npm install -g @anthropic/claude-code"
  output_failure_data "claude-code" "https://www.npmjs.com/package/@anthropic/claude-code" "latest" "$manual_steps" "npm not found"
  exit 1
fi

# Install via npm
if ! npm install -g @anthropic/claude-code; then
  manual_steps="Install manually:
   npm install -g @anthropic/claude-code

View on npm:
   https://www.npmjs.com/package/@anthropic/claude-code"
  output_failure_data "claude-code" "https://www.npmjs.com/package/@anthropic/claude-code" "latest" "$manual_steps" "npm install failed"
  exit 1
fi
```

## Error Handling

Custom installers require careful error handling:

- Each step may fail differently
- Prerequisites may be missing
- Platform differences can cause unexpected failures
- Manual installation steps should be detailed and accurate

Always wrap critical operations:

```bash
if ! download_step; then
  output_failure_data ...
  exit 1
fi

if ! extract_step; then
  output_failure_data ...
  exit 1
fi

if ! install_step; then
  output_failure_data ...
  exit 1
fi
```

## Important Notes

1. **Platform detection**: Use `detect_os()` and `detect_arch()` from platform-detection.sh

2. **Prerequisites**: Document and check for prerequisites before attempting installation

3. **Cleanup**: Clean up temp files (use `trap` for reliable cleanup)

4. **sudo usage**: Minimize sudo usage, only when absolutely necessary

5. **Manual steps**: Provide comprehensive manual installation instructions including:
   - Direct download links
   - All required steps in order
   - Platform-specific variations
   - Verification commands

## Common Issues

**Issue**: Prerequisites missing

- **Solution**: Check for prerequisites, provide installation instructions

**Issue**: Platform-specific failures

- **Solution**: Test on all platforms, handle differences explicitly

**Issue**: Download URL changes

- **Solution**: Use version APIs when available, provide fallback URLs

**Issue**: Complex multi-step installations

- **Solution**: Break into functions, error check each step

**Issue**: Tool requires sudo

- **Solution**: Document why sudo is needed, minimize scope
