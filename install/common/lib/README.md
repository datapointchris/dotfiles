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

### version-helpers.sh

Version comparison and GitHub API lookups shared by the release installers.

**Functions:**

- `version_compare(current, latest)` - 0 when equal, 1 when current is older, 2 when newer
- `github_token()` - Resolve a token from `GITHUB_TOKEN` or `gh auth token`, if either is available
- `fetch_github_latest_version(repo)` - Latest release tag from the GitHub API

### installed-versions.sh

Queries for what is currently installed, one per distribution mechanism. Sourced by `update.sh`,
which diffs a before/after snapshot to decide what to report.

These exist only for update commands that exit 0 whether or not anything changed and print nothing
distinguishing — `uv tool upgrade`, `npm update -g`, tpm's `update_plugins`, `:Lazy update`. For
those, observed state is the only thing that separates "updated" from "nothing to do". A phase that
converges through the CLI needs none of them: a `Change` says what moved and why.

Deliberately **not** used for brew/pacman/apt, rustup, `uv self update`, the `theme`/`font` update
commands, or the GitHub release installers. Those already report their own outcome accurately (the
release installers by comparing the installed version against the release tag before downloading),
and re-deriving a result they already state is duplicated logic that can only drift.

**Functions:**

- `uv_tool_installed_ref(tool)` - `<version> (<commit>)` from the tool's dist-info and PEP 610
  `direct_url.json`; the commit matters because the git-installed tools routinely upgrade without
  their version string moving
- `npm_global_versions()` - `<package> <version>` per line for every top-level global package
- `git_checkout_commit(dir)` - Short HEAD of a git checkout, or non-zero when the path is not one
- `git_checkouts_snapshot(parent_dir)` - `<name> <commit>` per line for every checkout directly
  inside a directory, for clone-per-thing managers like tpm and lazy.nvim; the checkouts rather than
  a lockfile, which only moves when upstream does and so misses a repair
- `uv_tool_pinned_rev(tool)` - The release a git-installed tool's receipt pins, empty when it tracks
  a branch; the pin, not the version, is what says whether `uv tool upgrade` can move it

### uv-git-tools.sh

Installing the personal Python CLIs that ship from a git repo rather than PyPI (`git_uv_tools`).
Sourced by `update.sh`, which is the update half. The install half is
`src/dotfiles/providers/uvtool.py`, which resolves the same pin from the same API.

These installs are pinned to a release tag, because each tool's own `pyselfupdate`-based updater
reads uv's receipt to decide what it may do: a git requirement with no `rev=` is a dev checkout, so
the tool never prints an update notice and refuses to reinstall over itself. Pinning here writes the
same receipt shape `<tool> update` writes, so the two agree instead of undoing each other, and both
resolve the version from the same releases API. The cost of getting this wrong is silent: a pinned
receipt makes `uv tool upgrade` a permanent no-op that still reports "already at latest", which hid
eight syncer releases.

**Functions:**

- `github_slug_from_url(url)` - `owner/name` from an https or ssh clone URL; non-zero for any other
  host, which has no releases API to ask
- `uv_git_tool_latest_ref(repo)` - Newest release tag of a tool's repo
- `uv_git_tool_requirement(tool, repo, ref)` - `<tool> @ git+<repo>@<ref>`, the requirement that
  installs one release; the leading name is what makes the receipt readable afterwards

## Architecture

These libraries provide utilities FOR installer scripts:

```yaml
installer script (plugins/tmux-plugins.sh)
    ↓ sources
common/lib/ utilities
    - failure-logging.sh (error reporting)
    - version-helpers.sh (version comparison, GitHub API)
    - installed-versions.sh (what is installed right now, for update reporting)
    - uv-git-tools.sh (release-pinned installs of the git-hosted Python CLIs)
```

**Key distinction:**

- **install/platform-detection.sh, install/run-installer.sh** - Sourced by install.sh (controls HOW installers run)
- **common/lib/** - Sourced by installer scripts (provides utilities FOR installers)

All installer scripts should source `failure-logging.sh` to ensure consistent error reporting that `run-installer.sh` can parse.
