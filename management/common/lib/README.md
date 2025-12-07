# Installer Utility Libraries

Shared libraries sourced by individual installer scripts for common installation patterns.

## Files

### failure-logging.sh

Outputs structured failure data in a format that `run-installer.sh` can parse and log.

**Function:**

- `output_failure_data(tool_name, download_url, version, manual_steps, reason)`

**Usage:**

```bash
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

if ! curl -fsSL "$URL" -o "$TARBALL"; then
  manual_steps="1. Download in your browser:
   $URL

2. Extract and install:
   tar -xzf ~/Downloads/tool.tar.gz
   mv tool ~/.local/bin/

3. Verify:
   tool --version"

  output_failure_data "tool-name" "$URL" "v1.0" "$manual_steps" "Download failed"
  exit 1
fi
```

**Output Format:**

```bash
FAILURE_TOOL='tool-name'
FAILURE_URL='https://...'
FAILURE_VERSION='v1.0'
FAILURE_REASON='Download failed'
FAILURE_MANUAL_START
1. Download in your browser...
...
FAILURE_MANUAL_END
```

This output goes to stderr and is captured by `run-installer.sh` for centralized failure logging.

### github-release-installer.sh

Helper functions for installing binaries from GitHub releases.

**Functions:**

- `get_platform_arch(darwin_x86, darwin_arm, linux_x86)` - Platform/arch string with custom capitalization
- `get_latest_version(repo)` - Fetch latest release tag from GitHub API
- `should_skip_install(binary_path, binary_name)` - Check if already installed
- `install_from_tarball(binary, url, path_in_tarball, version)` - Download/extract/install from .tar.gz
- `install_from_zip(binary, url, path_in_zip, version)` - Download/extract/install from .zip

**Usage:**
See `docs/architecture/github-release-installer.md` for detailed documentation.

### font-installer.sh

Complete font installation workflow for Nerd Fonts and other font families.

**Functions:**

- `get_system_font_dir()` - Platform-specific font directory
- `is_font_installed(font_name, font_dir)` - Check if font exists
- `download_nerd_font(package, download_dir, font_ext)` - Download and extract
- `prune_font_family(download_dir, prune_patterns)` - Remove unwanted variants
- `standardize_font_family(download_dir)` - Rename spaces to dashes
- `install_font_files(download_dir, font_ext, system_font_dir)` - Copy to system
- `refresh_font_cache(platform, font_name)` - Run fc-cache on Linux

**Usage:**
All 25+ font installer scripts use this library for consistent font installation. See `management/common/install/fonts/` for examples.

## Architecture

These libraries provide utilities FOR installer scripts:

```yaml
installer script (github-releases/lazygit.sh)
    ↓ sources
common/lib/ utilities
    - failure-logging.sh (error reporting)
    - github-release-installer.sh (GitHub release helpers)
    - font-installer.sh (font installation workflow)
```

**Key distinction:**

- **orchestration/** - Sourced by install.sh (controls HOW installers run)
- **common/lib/** - Sourced by installer scripts (provides utilities FOR installers)

All installer scripts should source `failure-logging.sh` to ensure consistent error reporting that `run-installer.sh` can parse.
