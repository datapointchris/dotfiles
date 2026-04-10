# GitHub Releases vs System Packages

**Context**: Needed a decision framework for choosing between GitHub binary releases and system package managers when adding new tools to the dotfiles installation system.
**Date**: November 2025

## The Problem

No clear criteria for when to use GitHub release installers (download binary directly) versus system package managers (apt, pacman, brew). Ad-hoc decisions led to inconsistency — some stable tools used GitHub releases unnecessarily, while some fast-moving tools relied on lagging package managers.

## The Decision Framework

**Use GitHub Releases when:**

- Tool has frequent releases (>4/year)
- Security-critical tool that needs latest vulnerability data (e.g., trivy)
- Package managers lag significantly behind upstream
- Self-contained binary with no system dependencies
- Cross-platform consistency matters (same version on macOS + Linux)

**Use System Package Managers when:**

- Tool is stable/mature with infrequent releases
- All package managers ship the current version
- Tool has system dependencies or integration requirements
- Feature-complete with no active development

## Example

- **trivy** → GitHub releases: monthly releases, security scanner (stale vuln DB = missed CVEs), Homebrew lags 0-2 versions
- **mkcert** → system packages: last release April 2022, version 1.4.4 everywhere, feature-complete

## Key Learnings

- Default to system packages unless there's a specific reason not to — they handle updates automatically
- "Frequent releases" means the tool is actively evolving, not just patching
- Security tools are the strongest case for GitHub releases — stale versions have real consequences
- Use `install/common/lib/github-release-installer.sh` library for new GitHub release installers

## Related

- [Package Management Architecture](../architecture/package-management.md)
- [GitHub Release Installer](../architecture/github-release-installer.md)
