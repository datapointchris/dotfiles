# GitHub Release Installer Library

Function-based library for installing binaries from GitHub releases with minimal duplication and maximum flexibility.

## Philosophy

The GitHub release installer library follows the dotfiles philosophy:

- **Function-based helpers, not complex YAML parsing** - Configuration stays in installer scripts, explicit and inline
- **Handles common patterns through parameters** - Platform detection, version checking, archive extraction
- **No over-abstraction** - Each installer remains readable and customizable
- **Built on production-grade infrastructure** - Uses structured logging and error handling
- **Automatic cleanup** - Trap-based cleanup ensures no orphaned files

## Architecture

```text
management/common/lib/github-release-installer.sh  # Library functions
└── Sources: error-handling.sh, structured-logging.sh

management/common/install/github-releases/*.sh     # Individual installers
└── Configuration: Inline in each script
└── Pattern: Source library → Configure → Install
```

## Library Functions

### Platform Detection

```bash
# Get platform string with custom formatting
get_platform "Darwin" "Linux"          # → "Darwin" on macOS, "Linux" on Linux
get_platform "darwin" "linux"          # → "darwin" on macOS, "linux" on Linux

# Get architecture string with custom formatting
get_arch "x86_64" "arm64" "x86_64"     # → platform-specific arch

# Get combined platform_arch (most common pattern)
get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"
# → "Darwin_x86_64" on Intel Mac
# → "Darwin_arm64" on Apple Silicon
# → "Linux_x86_64" on Linux
```

### Version Handling

```bash
# Get latest GitHub release version
get_latest_version "jesseduffield/lazygit"  # → "v0.40.2"

# Strip 'v' prefix from version string
strip_v_prefix "v1.2.3"  # → "1.2.3"

# Check if current version meets minimum requirement
version_meets_minimum "1.2.3" "1.0.0"  # → returns 0 (success)
version_meets_minimum "0.9.0" "1.0.0"  # → returns 1 (failure)
```

### Installation Check

```bash
# Check if binary is already installed with acceptable version
# Returns 0 (skip install) or 1 (should install)

# Simple existence check (any version acceptable)
check_existing_installation "$HOME/.local/bin/duf" "duf"

# Version check with minimum requirement
check_existing_installation \
  "$HOME/.local/bin/lazygit" \
  "lazygit" \
  "lazygit --version 2>&1 | grep -oE 'version=[0-9.]+' | cut -d= -f2" \
  "0.40.2"
```

The version check extracts just the version number for comparison. The command should output a clean version like "1.2.3", not the full version output.

### Download and Extract

```bash
# Download with automatic retry and cleanup registration
download_release "$DOWNLOAD_URL" "/tmp/app.tar.gz" "app-name"

# Extract tarball (specific file or all)
extract_tarball "/tmp/app.tar.gz" "/tmp" "app"      # Extract specific file
extract_tarball "/tmp/app.tar.gz" "/tmp"            # Extract all

# Extract zip file
extract_zip "/tmp/app.zip" "/tmp/app-extract"
```

### Installation

```bash
# Install single binary
install_binary "/tmp/lazygit" "$HOME/.local/bin/lazygit"

# Install multiple binaries
install_binaries "/tmp" "$HOME/.local/bin" "tenv" "terraform" "tofu"

# Create symlink
create_binary_symlink \
  "$HOME/.local/nvim-macos-arm64/bin/nvim" \
  "$HOME/.local/bin/nvim"
```

### Verification

```bash
# Verify installation
verify_installation "lazygit" "lazygit --version | head -n1"
verify_installation "yazi"  # No version check
```

## Installer Script Pattern

Every installer script follows this structure:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source libraries (error handling includes structured logging)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

# ================================================================
# Configuration Section
# ================================================================

BINARY_NAME="app-name"
REPO="owner/repo"
VERSION="1.2.3"  # OR: VERSION=$(get_latest_version "$REPO")

# Platform detection
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")

# Build URL
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/v${VERSION}/app_${VERSION}_${PLATFORM_ARCH}.tar.gz"

# Paths
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
TEMP_TARBALL="/tmp/${BINARY_NAME}.tar.gz"

# ================================================================
# Installation Section
# ================================================================

print_banner "Installing App Name"

# Check existing installation
VERSION_CMD="app --version | grep -oE '[0-9.]+' | head -n1"
if check_existing_installation "$TARGET_BIN" "$BINARY_NAME" "$VERSION_CMD" "$VERSION"; then
  exit_success
fi

log_info "Target version: v$VERSION"

# Check alternate installations
check_alternate_installation "$TARGET_BIN" "$BINARY_NAME"

# Download → Extract → Install → Verify
download_release "$DOWNLOAD_URL" "$TEMP_TARBALL" "$BINARY_NAME"
extract_tarball "$TEMP_TARBALL" "/tmp" "$BINARY_NAME"
install_binary "/tmp/$BINARY_NAME" "$TARGET_BIN"
verify_installation "$BINARY_NAME" "$VERSION_CMD"

print_banner_success "App Name installation complete"
exit_success
```

## Real-World Examples

### Example 1: LazyGit (Pinned Version, Tarball)

```bash
BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
VERSION="0.40.2"  # Pinned version

# LazyGit format: lazygit_0.40.2_Darwin_x86_64.tar.gz
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/v${VERSION}/lazygit_${VERSION}_${PLATFORM_ARCH}.tar.gz"

# Binary is at root of tarball
extract_tarball "$TEMP_TARBALL" "/tmp" "$BINARY_NAME"
install_binary "/tmp/$BINARY_NAME" "$TARGET_BIN"
```

### Example 2: Yazi (Latest Version, Zip, Nested Directory, Multiple Binaries)

```bash
BINARY_NAME="yazi"
REPO="sxyazi/yazi"
LATEST_VERSION=$(get_latest_version "$REPO")

# Yazi format: yazi-x86_64-apple-darwin.zip
ARCH=$(uname -m)
if [[ "$OSTYPE" == "darwin"* ]]; then
  YAZI_TARGET="${ARCH}-apple-darwin"
else
  YAZI_TARGET="${ARCH}-unknown-linux-gnu"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/yazi-${YAZI_TARGET}.zip"

# Extract zip, binaries in nested dir
EXTRACT_DIR="/tmp/yazi-${YAZI_TARGET}"
extract_zip "$TEMP_ZIP" "/tmp"
install_binary "$EXTRACT_DIR/yazi-${YAZI_TARGET}/yazi" "$TARGET_BIN"
mv "$EXTRACT_DIR/yazi-${YAZI_TARGET}/ya" "$HOME/.local/bin/ya"
```

### Example 3: Custom Platform Detection

For tools with non-standard naming conventions:

```bash
# Duf uses lowercase: duf_0.8.1_darwin_x86_64.tar.gz
PLATFORM=$(get_platform "darwin" "linux")
ARCH=$(get_arch "x86_64" "arm64" "x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/duf_${VERSION#v}_${PLATFORM}_${ARCH}.tar.gz"
```

## Version Checking Best Practices

### Extract Clean Version Numbers

Version check commands should output just the version number for comparison:

```bash
# ❌ BAD - Returns full output line
VERSION_CMD="lazygit --version | head -n1"
# Output: "commit=..., version=0.40.2, os=darwin, ..."

# ✅ GOOD - Extracts just version number
VERSION_CMD="lazygit --version 2>&1 | grep -oE 'version=[0-9.]+' | cut -d= -f2"
# Output: "0.40.2"

# ✅ GOOD - For different format
VERSION_CMD="yazi --version | grep -oE 'Yazi [0-9.]+' | cut -d' ' -f2"
# Output: "25.5.31"
```

### When to Use Minimum Version vs Exact Match

```bash
# Use minimum version for pinned releases
# (allows newer versions to satisfy requirement)
check_existing_installation "$BIN" "app" "$VERSION_CMD" "1.0.0"
# Current 1.5.0 >= 1.0.0 → Skip install ✓
# Current 0.9.0 < 1.0.0  → Install ✓

# Skip version check for "latest" installers
# (reinstalls every time unless file exists)
check_existing_installation "$BIN" "app"
# File exists → Skip install ✓
# File missing → Install ✓
```

## Configuration Patterns

### Inline Configuration (Recommended)

Configuration lives in the installer script itself:

```bash
# ================================================================
# Configuration
# ================================================================

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
VERSION="0.40.2"
```

**Advantages**:

- Explicit and self-documenting
- Easy to customize per-tool
- No YAML parsing overhead
- Clear what the script does at a glance

### When to Use packages.yml

Use `packages.yml` only when:

- Configuration is shared across multiple contexts (Task, Brewfile, apt lists)
- Version pinning needs central management
- You need to query configuration from multiple tools

For GitHub-specific settings (platform detection, URL patterns), inline configuration is better.

## Error Handling and Cleanup

The library automatically handles cleanup through error-handling.sh:

```bash
# Cleanup is automatic via trap handlers
download_release "$URL" "/tmp/app.tar.gz" "app"  # Registers cleanup
extract_tarball "/tmp/app.tar.gz" "/tmp"         # Registers cleanup
# If script fails, cleanup runs automatically
# If script succeeds, cleanup runs on exit
```

No need to manually register cleanup for library functions - they handle it internally.

## Migration from Old Pattern

### Before (95 lines)

```bash
#!/usr/bin/env bash
set -euo pipefail

source "$HOME/dotfiles/platforms/common/shell/formatting.sh"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=duf --field=repo)

# 15 lines of platform detection
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM_ARCH="darwin_x86_64"
  else
    PLATFORM_ARCH="darwin_arm64"
  fi
else
  PLATFORM_ARCH="linux_x86_64"
fi

# 20 lines of version checking
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$DUF_BIN" ]]; then
  CURRENT_VERSION=$(duf --version 2>&1 | head -n1)
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# 30 lines of download/extract/install
LATEST_VERSION=$(get_latest_github_release "$REPO")
DUF_URL="https://..."
if ! download_file "$DUF_URL" "$DUF_TARBALL" "duf"; then
  print_manual_install ...
  exit 1
fi
tar -xzf "$DUF_TARBALL" -C /tmp duf
mv /tmp/duf "$DUF_BIN"
chmod +x "$DUF_BIN"
rm -f "$DUF_TARBALL"

# 10 lines of verification
if command -v duf >/dev/null 2>&1; then
  print_success "Installed: $version"
else
  print_error "Installation failed"
  exit 1
fi
```

### After (60 lines with comments)

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

# ================================================================
# Configuration
# ================================================================

BINARY_NAME="duf"
REPO="muesli/duf"
LATEST_VERSION=$(get_latest_version "$REPO")

PLATFORM_ARCH=$(get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/duf_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
TEMP_TARBALL="/tmp/${BINARY_NAME}.tar.gz"

# ================================================================
# Installation
# ================================================================

print_banner "Installing Duf"

VERSION_CMD="duf --version | head -n1"
if check_existing_installation "$TARGET_BIN" "$BINARY_NAME" "$VERSION_CMD"; then
  exit_success
fi

log_info "Target version: $LATEST_VERSION"
check_alternate_installation "$TARGET_BIN" "$BINARY_NAME"

download_release "$DOWNLOAD_URL" "$TEMP_TARBALL" "$BINARY_NAME"
extract_tarball "$TEMP_TARBALL" "/tmp" "$BINARY_NAME"
install_binary "/tmp/$BINARY_NAME" "$TARGET_BIN"
verify_installation "$BINARY_NAME" "$VERSION_CMD"

print_banner_success "Duf installation complete"
exit_success
```

**Improvements**:

- 37% smaller (95 → 60 lines including comments and whitespace)
- Automatic cleanup (trap-based)
- Structured logging
- Better error handling
- More consistent pattern
- Easier to maintain

## Testing

Test an installer script:

```bash
# Test with existing installation (should skip)
bash management/common/install/github-releases/lazygit.sh

# Test force reinstall
FORCE_INSTALL=true bash management/common/install/github-releases/lazygit.sh

# Test with structured logging to file
bash management/common/install/github-releases/lazygit.sh 2>&1 | tee install.log

# Verify cleanup works (check /tmp before and after)
ls /tmp/*lazygit* 2>/dev/null || echo "Cleanup successful"
```

## Related Documentation

- `docs/architecture/error-handling.md` - Error handling library details
- `docs/architecture/structured-logging.md` - Logging system documentation
- `management/common/lib/program-helpers.sh` - Legacy helpers (being phased out)
