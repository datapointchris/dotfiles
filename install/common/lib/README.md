# Installer Utility Libraries

Shared libraries sourced by individual installer scripts for common installation patterns.

## Files

### failure-logging.sh

Outputs structured failure data in a format that `run-installer.sh` can parse and log.

**Function:**

- `output_failure_data(tool_name, download_url, version, manual_steps, reason)`

**Usage:**

```bash
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

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

### version-helpers.sh

Version comparison and GitHub API lookups shared by the release installers.

**Functions:**

- `version_compare(current, latest)` - 0 when equal, 1 when current is older, 2 when newer
- `parse_version(text)` - Extract a version string from arbitrary command output
- `github_token()` - Resolve a token from `GITHUB_TOKEN` or `gh auth token`, if either is available
- `fetch_github_latest_version(repo)` - Latest release tag from the GitHub API

### installed-versions.sh

Queries for what a package manager currently has installed. Sourced by `update.sh`, which diffs a
before/after snapshot to decide what to report: `uv tool upgrade`, `cargo binstall`, and
`npm update -g` all exit 0 whether or not anything changed, so an exit code alone cannot
distinguish a no-op from a real upgrade.

**Functions:**

- `uv_tool_installed_ref(tool)` - `<version> (<commit>)` from the tool's dist-info and PEP 610
  `direct_url.json`; the commit matters because the git-installed tools routinely upgrade without
  their version string moving
- `cargo_installed_version(crate)` - Installed version of a crate, or non-zero when the crate is not
  cargo-managed on this platform
- `npm_global_versions()` - `<package> <version>` per line for every top-level global package

## Architecture

These libraries provide utilities FOR installer scripts:

```yaml
installer script (github-releases/lazygit.sh)
    ↓ sources
common/lib/ utilities
    - failure-logging.sh (error reporting)
    - github-release-installer.sh (GitHub release helpers)
    - version-helpers.sh (version comparison, GitHub API)
    - installed-versions.sh (what is installed right now, for update reporting)
```

**Key distinction:**

- **install/platform-detection.sh, install/run-installer.sh** - Sourced by install.sh (controls HOW installers run)
- **common/lib/** - Sourced by installer scripts (provides utilities FOR installers)

All installer scripts should source `failure-logging.sh` to ensure consistent error reporting that `run-installer.sh` can parse.
