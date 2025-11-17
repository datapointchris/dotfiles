# Nerd Fonts Reference

Quick reference for installing Nerd Fonts across platforms.

## Why Nerd Fonts?

Required for proper terminal icons and glyphs in tmux, neovim, yazi, and other CLI tools.

## Recommended Fonts

- **FiraCode Nerd Font** - Ligatures, excellent for coding
- **JetBrainsMono Nerd Font** - Designed for developers
- **Hack Nerd Font** - Clean, readable
- **CascadiaCode Nerd Font** - Microsoft's coding font
- **Meslo Nerd Font** - macOS default terminal compatible

## Download

Get fonts from [nerdfonts.com](https://www.nerdfonts.com/)

Download the font family zip, extract, and install.

## Installation

### macOS

**Option 1** - Double-click:

1. Open extracted font files
2. Double-click to open Font Book
3. Click "Install Font"

**Option 2** - Command line:

```sh
cp /path/to/fonts/*.{ttf,otf} ~/Library/Fonts/
```

Fonts installed to `~/Library/Fonts/` are user-specific.

### WSL Ubuntu

**Option 1** - Install in Windows (easiest):

1. Right-click font files
2. "Install for all users"
3. WSL automatically has access

**Option 2** - Install in WSL:

```sh
mkdir -p ~/.local/share/fonts
cp /path/to/fonts/*.{ttf,otf} ~/.local/share/fonts/
fc-cache -fv
```

### Linux (native)

```sh
mkdir -p ~/.local/share/fonts
cp /path/to/fonts/*.{ttf,otf} ~/.local/share/fonts/
fc-cache -fv
```

System-wide installation (requires sudo):

```sh
sudo cp /path/to/fonts/*.{ttf,otf} /usr/local/share/fonts/
sudo fc-cache -fv
```

## Verification

List installed Nerd Fonts:

**macOS**:

```sh
fc-list | grep -i "nerd\|fira.*code\|jetbrains.*mono" | cut -d: -f2 | sort -u
```

**Linux/WSL**:

```sh
fc-list | grep -i "nerd" | cut -d: -f2 | sort -u
```

## Terminal Configuration

After installing fonts, configure your terminal to use them:

- **iTerm2**: Preferences → Profiles → Text → Font
- **Ghostty**: Edit `~/.config/ghostty/config` → `font-family = "FiraCode Nerd Font"`
- **Alacritty**: Edit `~/.config/alacritty/alacritty.yml` → `font.normal.family`
- **Windows Terminal**: Settings → Profiles → Appearance → Font face

Restart your terminal after changing fonts.

## Storage Location

Font files are typically large (2-5MB each). Store them outside the dotfiles repo:

- Personal backup location (not in git)
- Cloud storage (Dropbox, Google Drive, etc.)
- External drive for backups

## Troubleshooting

**Fonts not showing in terminal**:

- Verify font installed: `fc-list | grep FontName`
- Restart terminal application
- Check terminal font configuration

**Icons showing as boxes/question marks**:

- Terminal not using a Nerd Font
- Font configuration incorrect
- Font not installed properly

**WSL not seeing Windows fonts**:

- Ensure fonts installed "for all users" in Windows
- Check font installed: `fc-list | grep FontName` in WSL
