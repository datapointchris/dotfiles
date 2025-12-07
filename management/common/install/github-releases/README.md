# GitHub Release Installers

## Pattern

This directory contains installers for tools distributed as binary releases on GitHub. These scripts download pre-compiled binaries from GitHub releases, extract them, and install to `~/.local/bin/`.

**Key characteristics**:

- Download from `https://github.com/{repo}/releases/download/{version}/{archive}`
- Platform-specific binary selection (Darwin_x86_64, Darwin_arm64, Linux_x86_64)
- Idempotent (skips if already installed)
- Structured error reporting via `output_failure_data()`

## When to Use

Add a new installer to this directory when:

- Tool is distributed as GitHub release with binary archives
- Release includes platform-specific builds (macOS x86/ARM, Linux)
- Archive contains a single binary (or binaries in predictable path)
- No compilation required

## Libraries Used

All scripts in this directory source:

```bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"
```

## Standard Pattern

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="toolname"
REPO="owner/repo"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing ToolName"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit 0
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/toolname_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "toolname" "$VERSION"
```

## Adding a New Tool

1. **Find the GitHub repo** and check releases page
   - Verify binary releases exist
   - Note the platform naming pattern (Darwin vs macOS, x86_64 vs amd64, etc.)
   - Check archive format (.tar.gz vs .zip)

2. **Create new script** named `toolname.sh`

3. **Configure variables**:

   ```bash
   BINARY_NAME="toolname"      # Name of the binary
   REPO="owner/repo"            # GitHub repository
   TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
   ```

4. **Configure platform strings** in `get_platform_arch()`:
   - Check GitHub releases for exact platform naming
   - Examples:
     - `"Darwin_x86_64" "Darwin_arm64" "Linux_x86_64"` (lazygit pattern)
     - `"darwin_amd64" "darwin_arm64" "linux_amd64"` (some tools)
     - `"macos-x86_64" "macos-arm64" "linux-x86_64"` (neovim pattern)

5. **Configure download URL**:
   - Use `${VERSION}` for version tag (includes 'v' prefix)
   - Use `${VERSION#v}` for version without 'v' prefix
   - Use `${PLATFORM_ARCH}` for platform string
   - Example patterns:

     ```bash
     # Pattern 1: version without 'v', underscore separator
     "lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

     # Pattern 2: version with 'v', dash separator
     "tool-${VERSION}-${PLATFORM_ARCH}.tar.gz"

     # Pattern 3: nested directory structure
     "tool/${VERSION}/tool_${PLATFORM_ARCH}.zip"
     ```

6. **Configure binary path in archive**:
   - For binary at root: `"toolname"`
   - For nested binary: `"toolname-dir/bin/toolname"`
   - For pattern-matched directory: `"toolname_*_${PLATFORM_ARCH}/toolname"`

7. **Choose archive function**:
   - `.tar.gz` files: `install_from_tarball`
   - `.zip` files: `install_from_zip`

8. **Test the installer**:

   ```bash
   # Test installation
   bash management/common/install/github-releases/toolname.sh

   # Verify binary is in PATH
   which toolname
   toolname --version

   # Test idempotency (should skip on second run)
   bash management/common/install/github-releases/toolname.sh
   ```

## Examples

### Simple tarball (lazygit.sh)

```bash
BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
VERSION=$(get_latest_version "$REPO")
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "lazygit" "$VERSION"
```

### Nested binary path (glow.sh)

```bash
BINARY_NAME="glow"
REPO="charmbracelet/glow"
VERSION=$(get_latest_version "$REPO")
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/glow_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"
# Binary is in subdirectory with platform name
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "glow_*_${PLATFORM_ARCH}/glow" "$VERSION"
```

### Zip archive (yazi.sh)

```bash
BINARY_NAME="yazi"
REPO="sxyazi/yazi"
VERSION=$(get_latest_version "$REPO")
PLATFORM_ARCH=$(get_platform_arch "x86_64-apple-darwin" "aarch64-apple-darwin" "x86_64-unknown-linux-gnu")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/yazi-${PLATFORM_ARCH}.zip"
install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "yazi-${PLATFORM_ARCH}/yazi" "$VERSION"
```

## Error Handling

The library functions handle errors automatically:

- Download failures are reported with manual installation instructions
- Missing binaries in PATH trigger warnings
- All failures call `output_failure_data()` for structured logging

No additional error handling needed in individual scripts.

## Common Issues

**Issue**: Platform naming doesn't match

- **Solution**: Check actual release files on GitHub, use exact naming

**Issue**: Binary not found after extraction

- **Solution**: Check archive structure, update binary path parameter

**Issue**: Version string mismatch (v1.0 vs 1.0)

- **Solution**: Use `${VERSION#v}` to strip 'v' prefix if needed

**Issue**: Tool has no ARM builds

- **Solution**: Provide x86_64 build for both ARM platforms (Rosetta translation)
