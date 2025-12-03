# Font Installation Scripts

Scripts for downloading and installing curated coding fonts.

## Overview

These scripts handle the one-time setup of downloading and installing coding fonts to your system. For day-to-day font management (changing fonts, tracking favorites, etc.), use the `font` CLI app.

## Scripts

### download.sh

Downloads 22 curated coding font families from GitHub releases.

**Usage**:

```bash
bash management/scripts/fonts/download.sh [OPTIONS] [directory]

# Or via Task
task fonts:download
```

**Features**:

- Downloads from official GitHub releases
- Prunes unwanted weight variants (keeps Regular/Bold/Italic/BoldItalic)
- Standardizes filenames for ImageMagick compatibility
- Phase control for interrupted downloads
- Single family downloads with `-f`

**Font Families** (22 total):

- JetBrains Mono, Cascadia Code, Meslo Nerd Font
- Monaspace (5 variants), Iosevka (6 variants)
- Victor Mono, Fira Code (2 variants), Commit Mono
- Comic Mono, Serious Shanns, Source Code Pro
- Terminus, Hack, IBM 3270, Roboto Mono
- Space Mono, Intel One Mono, Droid Sans

**Output**: `~/fonts/{family_name}/`

### install.sh

Installs downloaded fonts to platform-specific system directories.

**Usage**:

```bash
bash management/scripts/fonts/install.sh [OPTIONS]

# Or via Task
task fonts:install
```

**Platform Targets**:

- **macOS**: `~/Library/Fonts/`
- **Linux**: `~/.local/share/fonts/`
- **WSL**: `/mnt/c/Windows/Fonts/` (with manual fallback)

**Features**:

- Family-specific or all-at-once installation
- Exclusion list for problematic fonts
- Dry-run mode for testing
- Font cache refresh (Linux)
- WSL graceful fallback to manual instructions

## Task Automation

Two Task commands are available:

```bash
task fonts:download    # Download coding fonts from GitHub
task fonts:install     # Install fonts to system directory
```

## Typical Workflow

**First-time setup**:

```bash
task fonts:download    # Download fonts from GitHub
task fonts:install     # Install to system directory
```

**Update fonts** (get latest releases):

```bash
task fonts:download    # Re-download latest versions
task fonts:install     # Reinstall to system
```

**Add specific family**:

```bash
bash management/scripts/fonts/download.sh -f jetbrains
bash management/scripts/fonts/install.sh -f jetbrains
```

## WSL Considerations

WSL requires fonts to be installed on **Windows**, not in the WSL Linux environment. Windows Terminal renders fonts from the Windows font directory.

**Automated installation** (personal computers):

- Script attempts to copy fonts to `/mnt/c/Windows/Fonts/`
- Requires write permissions (administrator privileges)

**Manual installation** (work computers):

- If permissions denied, script provides Windows path for manual installation
- User drags/drops font files to Windows Settings → Fonts
- More reliable on restricted corporate environments

## Font Management App

After installation, use the `font` CLI app for daily font management:

```bash
font change           # Interactive font picker with previews
font like "reason"    # Mark favorites
font rank             # See most liked fonts
font log              # View usage history
```

See `apps/common/font/README.md` for full font management documentation.

## Migration Notes

These scripts were previously part of the `font` app (`apps/common/font/commands/`). They've been moved to `management/scripts/fonts/` to better separate:

- **Setup concerns** (one-time download/install) → management/
- **Runtime concerns** (daily font management) → font app

Old commands (`font download`, `font install`) now show deprecation warnings directing users to the new Task commands.

## Related Files

- `apps/common/font/` - Font management CLI app
- `Taskfile.yml` - Task automation (fonts:download, fonts:install, fonts:setup)
- `docs/tools/registry.yml` - Font app documentation
