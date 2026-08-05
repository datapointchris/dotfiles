# GitHub Release Installer Library

## Overview

The GitHub Release Installer library provides focused helper functions for installing binary tools from GitHub releases. It eliminates code duplication across the installer scripts in `install/common/github-releases/` while maintaining clarity and simplicity.

## Design Philosophy

The library follows the "medium abstraction" principle:

- **Focused helpers** - Only abstract truly repetitive patterns
- **Inline complexity** - Single-use operations stay inline in functions
- **Explicit configuration** - Each script contains its own configuration inline
- **No YAML complexity** - Avoid complex packages.yml parsing for variations
- **Straightforward** - Easy to trace and understand what's happening

## Architecture

### Library Chain

```text
installer-script.sh
  └─> error-handling.sh (set -euo pipefail, traps, cleanup)
       └─> logging.sh (status messages with [LEVEL] prefixes)
            └─> colors.sh
```

Each installer script sources `error-handling.sh`, which automatically provides:

- Error safety with `set -euo pipefail`
- Trap handlers for cleanup
- Structured logging (auto-detects terminal vs pipe)
- Consistent error messages with file:line references

### Library Functions

Located in `install/common/lib/github-release-installer.sh`:

#### 1. `get_platform_arch()`

Handles platform/architecture detection with customizable capitalization.

**Usage:**

```bash
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
```

**Why it exists:** Different GitHub projects use different naming conventions:

- `lazygit`: `Darwin_x86_64`
- `duf`: `darwin_x86_64` (lowercase)
- `zk`: `macos-x86_64` (different platform name)

#### 2. `get_latest_version()`

Fetches the latest release version from GitHub API.

**Usage:**

```bash
VERSION=$(get_latest_version "owner/repo")
# Returns: v1.2.3
```

**Why it exists:** Every installer needs to fetch versions, same pattern every time.

#### 3. `should_skip_install()`

Checks if installation should be skipped (already installed, unless FORCE_INSTALL=true).

**Usage:**

```bash
if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi
```

**Why it exists:** Idempotency check used by every installer.

#### 4. `install_from_tarball()`

Complete installation pattern for tar.gz archives.

**What it does:**

1. Downloads tarball to /tmp
2. Registers cleanup trap
3. Verifies the download against the release's published SHA-256
4. Extracts archive
5. Moves binary to ~/.local/bin
6. Sets executable permissions
7. Verifies installation

Step 3 precedes extraction deliberately, so unverified bytes are never parsed by `tar`. It also
covers the offline-cache path, where a stale or truncated file is likelier than a fresh download.
See "Checksum Verification" below.

**Usage:**

```bash
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "path/in/tarball"
```

**Why it's one function:** Download, extract, install, verify are always done together. Splitting them into separate functions creates unnecessary indirection.

#### 5. `install_from_zip()`

Same as `install_from_tarball()` but for zip files.

**Usage:**

```bash
install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "path/in/zip"
```

#### 6. `get_os()`

Returns `"darwin"` or `"linux"` based on `$OSTYPE`.

**Usage:**

```bash
OS=$(get_os)
```

**Why it exists:** Every standard installer needs OS detection before constructing the download URL. Eliminates the repeated inline one-liner.

#### 7. `get_arch()`

Returns normalized architecture string: `x86_64` or `arm64` (converts `aarch64` → `arm64`).

**Usage:**

```bash
ARCH=$(get_arch)
```

**Why it exists:** The `uname -m | sed 's/aarch64/arm64/...'` chain was copy-pasted across standard installers. A `case` statement in the library is clearer and has one canonical definition.

## Script Patterns

### Simple Tarball Installer

Most common pattern (majority of tools):

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/install/common/lib/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing LazyGit"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "lazygit"

print_banner_success "LazyGit installation complete"
exit_success
```

**Lines:** ~40-50 (was 90-120)

### Custom Installer (Special Cases)

Some tools need custom handling:

- **yazi**: Installs multiple binaries (yazi + ya), adds plugins
- **tenv**: Installs 7 binaries (tenv + proxy binaries)
- **terraformer**: Downloads raw binary (no archive)
- **zk**: Complex platform detection (macos vs linux, different arch naming)

These scripts use library helpers where applicable but handle their unique requirements inline.

## Bundler Contract

`install/offline/create-bundle.sh` invokes each script with two read-only flags to build the offline cache without performing any installation on the bundler's host:

- `--print-url <os> <arch>` — required. Emits one line: `name|version|url`. The bundler downloads `url` into `installers/binaries/`. See `install/common/github-releases/lazygit.sh` for the canonical implementation.
- `--print-extras <os> <arch>` — optional. Emits zero or more lines in the same `name|version|url` format for companion files that aren't included in the release tarball. The bundler downloads each into `installers/binaries/` alongside the main artifact. The fzf installer uses this for `fzf-tmux`, the popup wrapper script that the tmux `prefix+s` binding calls — it lives in the fzf repo but is not bundled into release tarballs.

Both flags must be handled *before* the script sources logging/error-handling libraries and before any installation logic, so invocation is fast and side-effect-free. The bundler grep-detects `--print-extras` support before invoking it; scripts without the flag are skipped (calling them would otherwise fall through to their full install path).

The version returned by `--print-extras` should be pinned to the same release as `--print-url` so the bundle ships a matched pair. Compute the version once in the script and reuse it for both URL builders.

The bundle also carries `installers/manifest.txt`, which is where an offline install reads each tool's version. `OFFLINE_MODE=true` makes both fetch helpers in `version-helpers.sh` resolve from it instead of the API — necessary because the asset filename is built from the version, so a version fetched live names a file the bundle does not contain the moment upstream ships a release. The short-circuit is keyed on `BINARY_NAME`, which every installer sets before resolving a version.

## Bundle Download Cache

Rebuilding a bundle used to re-download every asset even when most releases had not moved. `create-bundle.sh` now keeps what it fetches under `$XDG_CACHE_HOME/dotfiles/offline-bundle/`, at a path mirroring the asset URL so an entry can be read, inspected, and deleted per repo without a lookup table. This is the bundler's own cache on the machine building the bundle, distinct from `installers/` inside the bundle itself.

The URL is the cache key, and that is the whole design. A release asset's URL names its version, so while upstream has not moved the same URL resolves to the same bytes; the moment a release ships, the URL changes and the entry misses on its own. There is no staleness heuristic, no TTL on correctness, and nothing to invalidate by hand.

Install scripts are excluded deliberately. Every one of them is served from an unversioned URL — an installer endpoint or a `main`-branch raw file — so a URL-keyed hit would pin whatever was current the first time and never update. They are a few KB each, so there is nothing to win by caching them either.

Each cached asset carries two sidecars:

- `<asset>.sha256` — the digest of the bytes as they were cached, recomputed and compared on every hit. A corrupted or tampered entry is evicted and re-downloaded rather than shipped into a bundle.
- `<asset>.checksum-status` — `verified` or `unpublished`, recording what asking upstream for a checksum returned. That question costs a release API call plus a download, and its answer cannot change for a published tag, so it caches as safely as the asset does.

Entries age out on last use rather than on age (`CACHE_RETENTION_DAYS` in the script), so a tool that never changes survives precisely because the cache kept working for it, while superseded versions fall away. The sweep runs after the tarball is written, so housekeeping can never delay or fail a build. `--no-cache` bypasses the cache entirely for a build that must fetch everything fresh.

## Code Savings

The library reduced per-script boilerplate by roughly half compared to the pre-library era, where each script duplicated platform detection, version fetching, download, and installation logic. The previous iteration (401 lines, 16 functions) was over-abstracted; the current library has 7 focused functions.

See `install/common/github-releases/` for all current scripts.

## Custom Installers (Not Using Library)

Some tools have unique requirements that don't fit the GitHub release pattern. These live in `install/common/custom-installers/` instead. All still use error-handling.sh for structured logging consistency.

## Private Repositories

The browser download URL (`github.com/<owner>/<repo>/releases/download/...`) returns 404 for a private repository no matter what credentials accompany it. Only the REST asset endpoint serves those, and only when the request carries `Accept: application/octet-stream` alongside a token.

`download_release_asset` handles this: when a token is available it resolves the asset id for the tag and fetches through the REST endpoint, otherwise it falls back to the browser URL, which is all a public repo needs. `install_from_tarball` derives the repo and tag from the download URL rather than taking new parameters, so every existing installer inherits the behavior unchanged.

Token resolution lives in `github_token` — `GITHUB_TOKEN` if exported, otherwise whatever `gh auth token` reports. `gh` is only ever a source of credentials here; the transfer itself is always curl.

## Prefixed Release Tags

A repository whose primary artifact is not the CLI cannot use `/releases/latest` to find the CLI's release — that endpoint returns whichever release is newest overall, which may belong to the application. The personal data CLIs (`icb`, `learning`, `nomad`, `meso`) are nested Go modules released under a `cli/v*` tag for exactly this reason, so their installers call `fetch_github_latest_version_prefixed` instead, which lists releases and takes the newest whose tag carries the prefix.

The prefix is stripped before the version is used, so `cli/v1.2.0` compares as `v1.2.0` and expands `{version_num}` to `1.2.0`. The tag keeps its prefix only where it identifies the release itself — in the download URL.

## Design Decisions

### Why Not More Abstraction?

**Rejected:** Complex packages.yml with all download patterns

```yaml
# TOO COMPLEX - requires YAML parser, hard to trace
github_releases:
  - name: lazygit
    archive_format: tar.gz
    url_pattern: "{repo}/releases/download/{version}/lazygit_{version}_{platform}_{arch}.tar.gz"
    binary_pattern: "lazygit"
```

**Chosen:** Inline configuration in each script

```bash
# SIMPLE - easy to trace, self-contained
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"
```

**Rationale:** URL patterns vary enough that YAML templates become complex. Inline keeps it explicit and traceable.

### Why Not Version Checking?

**Rejected:** Minimum version requirements, complex version comparison

**Chosen:** Always install latest from GitHub API

**Rationale:**

- Simpler code
- Latest is usually what you want
- Can pin specific version by editing script if needed
- Reduces maintenance burden

### Why Inline Download/Extract/Install?

**Rejected:** Separate `download_release()`, `extract_tarball()`, `install_binary()` functions

**Chosen:** Single `install_from_tarball()` function with inline operations

**Rationale:**

- These operations are ALWAYS done together
- Separate functions create unnecessary indirection
- Harder to trace: installer → install_from_tarball → download_release → download_with_retry
- Inline is more straightforward

## Integration with Error Handling

The library assumes `error-handling.sh` has been sourced by the calling script. This provides:

### Automatic Cleanup

```bash
# In install_from_tarball()
register_cleanup "rm -f '$temp_tarball' 2>/dev/null || true"
```

Cleanup happens automatically on exit (success or failure).

### Error Context

```bash
log_fatal "Failed to download from $download_url" "${BASH_SOURCE[0]}" "$LINENO"
```

Errors include file:line references for debugging.

### Structured Logging

Auto-detects terminal vs pipe:

**Terminal mode:**

```text
  ● Downloading lazygit...
  ✓ lazygit installed successfully
```

**Structured mode (pipe/log):**

```text
[INFO] Downloading lazygit...
[INFO] ✓ lazygit installed successfully
```

## Adding a New Tool

### Steps

1. Create new script in `install/common/github-releases/`
2. Use template pattern (see Simple Tarball Installer above)
3. Configure: BINARY_NAME, REPO, download URL pattern
4. Handle special cases inline if needed
5. Test on all platforms

### Time Required

- **Before library:** 30-60 minutes (80-120 lines of boilerplate)
- **After library:** 5-10 minutes (40-50 lines, mostly copy-paste)

**6x faster**

## Testing

Run individual installer:

```bash
bash install/common/github-releases/lazygit.sh
```

Force reinstall:

```bash
FORCE_INSTALL=true bash install/common/github-releases/lazygit.sh
```

Test structured logging:

```bash
# Visual mode (terminal)
bash install/common/github-releases/lazygit.sh

# Structured mode (pipe)
bash install/common/github-releases/lazygit.sh 2>&1 | cat
```

## Checksum Verification

Every download is checked against the SHA-256 the release published, before extraction. This brings
the installers level with `goselfupdate`, which each tool's own `update` command already uses — the
two paths install the same binary and now trust it on the same terms.

**Finding the checksum file.** It is discovered from the release's asset list rather than guessed,
because the naming is not consistent across projects: `checksums.txt` (goreleaser), `SHA256SUMS`
(just), `<tool>_<version>_checksums.txt` (fzf, trivy), or a per-asset `<asset>.sha256` sidecar
(atuin, hadolint). A sidecar wins outright, since it names exactly one file and cannot be ambiguous.

Detached signatures and certificates sit beside the checksums file and match a naive `*checksum*`
search — tflint publishes `checksums.txt` next to `checksums.txt.keyless.sig` and `checksums.txt.pem`.
Those are excluded by suffix, or the asset would be compared against a signature.

**Reading it.** The `sha256sum` format both GNU and goreleaser emit: digest, whitespace, an optional
`*` binary marker, then the name. A CI step written as `sha256sum ./*.tar.gz` records `./tool.tar.gz`
while the asset is named `tool.tar.gz`, so an exact match is tried first and the base name only
consulted when nothing matched exactly. A case-insensitive match is the last resort: GitHub resolves
release asset paths case-insensitively, so lazygit downloads as `Linux_x86_64` while its checksums
file records `linux_x86_64`, and rejecting that discards a checksum the project did publish.

**Offline.** A cached file is verified against `installers/checksums.txt`, never the network —
discovering which asset holds a checksum costs a release API call, and the network a bundle exists
for is the one that blocks it. `create-bundle.sh` records only digests it verified against upstream
while building, so an asset whose release publishes nothing usable is absent from that file and
falls through to the normal path rather than being reported as verified. On a rebuild that digest
may be replayed from the [bundle download cache](#bundle-download-cache) instead of re-fetched — the
bytes were checked against upstream when first cached, and are re-checked against that digest on
every hit.

**On failure.** A mismatch deletes the download and aborts — never negotiable, and deleting matters
because `/tmp` is the offline cache path, so a retry would otherwise extract bytes that already
failed. A release publishing no checksum file at all is a different case, decided by the caller:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHECKSUM_REQUIRED` | `true` | `false` permits an install with a warning when upstream publishes nothing. Set only with a comment saying why. Currently `shellcheck`, `zk`, `win32yank`. |
| `CHECKSUM_URL` | unset | Names the checksums file directly, for a release not on GitHub where the asset list cannot be queried. Currently `terraform-ls`. |

Defaulting to required means a project that *starts* publishing checksums is covered automatically,
and one that *stops* fails loudly instead of silently downgrading.

**What this does and does not defend against.** It catches a corrupted, truncated, or intercepted
download, given that the checksums file itself arrives over TLS from the same release. It does not
defend against a compromised publishing account, which can rewrite the checksums file alongside the
asset — that needs a signature verified against a key distributed out of band.

## Future Improvements

### Possible (Low Priority)

- Signature verification for the releases that publish one (sigstore bundles: glow, tflint, trivy)
- Lightweight install log for audit trail (append-only)
- Helper for multi-binary installation pattern

### Not Recommended

- ❌ Complex packages.yml parsing - contradicts straightforward principle
- ❌ Automatic version checking/upgrades - adds complexity
- ❌ Rollback capability - idempotency is sufficient
- ❌ More abstraction layers - keep it simple

## Related Documentation

- [Error Handling](error-handling.md)
- [Shell Libraries](shell-libraries.md)
- Production-Grade Management Enhancements (planning doc)

## Files

**Library:**

- `install/common/lib/github-release-installer.sh`

**Converted Scripts:** See `install/common/github-releases/` for the full current listing.

**Moved to Custom Installers:**

- `install/common/custom-installers/awscli.sh` - Uses AWS custom installer
- `install/common/custom-installers/claude-code.sh` - Uses official installer script
- `install/common/custom-installers/terraform-ls.sh` - Uses releases.hashicorp.com (not GitHub)

**Moved back to GitHub Releases:**

- `install/common/github-releases/tenv.sh` - Terraform is a program, not a language. Grouped by installation method (GitHub releases)
