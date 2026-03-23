# Version Comparison in Shell

**Context**: Installer update scripts needed to compare semantic versions to decide whether to download a newer release or skip because the installed version is current.
**Date**: December 2025

## The Problem

Comparing semantic versions in bash is non-trivial. String comparison fails (`"1.9.0" > "1.10.0"` is true lexicographically but wrong semantically). Splitting on dots and comparing numerically works but is verbose and error-prone with pre-release suffixes.

## The Solution

Use GNU `sort -V` (version sort) which handles semantic versioning correctly:

```bash
version_compare() {
  local current="${1#v}"   # Strip 'v' prefix
  local latest="${2#v}"

  if [[ "$current" == "$latest" ]]; then
    return 0  # Same version
  elif [[ $(printf '%s\n' "$current" "$latest" | sort -V | head -n1) == "$current" ]]; then
    return 1  # Current is older (update available)
  else
    return 2  # Current is newer
  fi
}
```

## Key Learnings

- `sort -V` is available in GNU coreutils (macOS via Homebrew, standard on Linux) and handles all semver edge cases
- Always strip the `v` prefix before comparing (`v1.2.3` → `1.2.3`)
- Fail-safe default: if version check fails (API rate limit, missing binary, network error), proceed with installation rather than skipping — a redundant install is better than a stale binary
- Use `FORCE_INSTALL=true` to trigger version checking mode in installers (repurposes existing flag)
- See `management/common/lib/version-helpers.sh` for the canonical implementation

## Related

- [GitHub Releases vs System Packages](github-releases-vs-system-packages.md)
- [Package Management Architecture](../architecture/package-management.md)
