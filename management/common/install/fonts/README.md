# Font Installation Scripts

Scripts for downloading and installing curated coding fonts.

## Overview

These scripts handle the one-time setup of downloading and installing coding fonts to your system. For day-to-day font management (changing fonts, tracking favorites, etc.), use the `font` CLI app.

## Scripts

### nerd-fonts.sh

Installs Nerd Fonts defined in `packages.yml`.

```bash
# Install all Nerd Fonts
bash management/common/install/fonts/nerd-fonts.sh

# Install specific font by package name
bash management/common/install/fonts/nerd-fonts.sh Hack
```

**Nerd Fonts installed**: CascadiaCode, ComicShannsMono, FiraCode, Hack, Iosevka, JetBrainsMono, Meslo, Monaspace, RobotoMono

### Individual Font Installers

Each font has its own installer for fonts not in the Nerd Fonts collection:

- `commitmono.sh` - Commit Mono (GitHub release)
- `comicmononf.sh` - ComicMonoNF (xtevenx variant)
- `seriousshanns.sh` - SeriousShanns Nerd Font Mono
- `sgr-iosevka.sh` - SGr-Iosevka Term Slab (TTC collection)

## Platform Behavior

All installers use the shared `font-installer.sh` library which handles platform differences automatically:

| Platform | Font Directory | Additional Steps |
|----------|---------------|------------------|
| macOS | `~/Library/Fonts/` | None (automatic) |
| Linux | `~/.local/share/fonts/` | `fc-cache` refresh |
| WSL | Windows user fonts dir | Registry registration |

### WSL Automatic Installation

On WSL, fonts are installed directly to Windows so Windows Terminal can use them:

1. Fonts are copied to `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (user fonts, no admin required)
2. Registry entries are created in `HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts`
3. Fontconfig is configured to see Windows fonts (via `fontconfig-setup.sh`)

This happens automatically during `./install.sh` - no manual steps required.

## Offline Installation

All installers support offline mode for corporate environments where GitHub is blocked:

1. **Create offline bundle** (on machine with internet):

   ```bash
   ./install.sh --create-offline-bundle --with-fonts
   ```

2. **Transfer** the bundle to restricted machine

3. **Install** with offline flag:

   ```bash
   ./install.sh --machine wsl-work-workstation --offline
   ```

The offline cache location is `~/installers/fonts/`. Installers check this location before attempting downloads.

## Shared Library

All font installers use `management/common/lib/font-installer.sh` which provides:

- `get_system_font_dir()` - Platform-aware font directory
- `install_font_files()` - Copy + register (WSL registry integration)
- `refresh_font_cache()` - Platform-appropriate cache refresh
- `prune_font_family()` - Remove unwanted weight variants
- `fix_font_metadata()` - Fix Kitty/Ghostty compatibility issues
- `check_font_cache()` - Offline cache support

## Integration with install.sh

Fonts are installed during the main installation when `fonts: true` in the machine manifest:

```yaml
# management/machines/wsl-work-workstation.yml
fonts: true
```

The install order ensures WSL fontconfig setup runs before font installation.

## Related Files

- `management/common/lib/font-installer.sh` - Shared installation library
- `management/wsl/install/fontconfig-setup.sh` - WSL fontconfig for Windows fonts
- `management/wsl/lib/install-windows-font.sh` - Standalone WSL font installer
- `management/packages.yml` - Nerd Fonts definitions
- `docs/apps/font.md` - Font CLI tool documentation
