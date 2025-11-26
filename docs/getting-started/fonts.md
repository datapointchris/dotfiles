# Installing Nerd Fonts

Quick reference for installing and configuring Nerd Fonts across platforms.

## What Are Nerd Fonts?

Nerd Fonts patches popular programming fonts with 3,600+ icons and glyphs from Font Awesome, Material Design Icons, Octicons, Powerline symbols, and more. These icons enable rich visual interfaces in terminal emulators, Neovim, tmux, file managers (yazi, ranger), and shell prompts (starship).

Without Nerd Fonts, icons display as empty boxes (☐) or question marks (?).

## Which Fonts to Install

Start with one or two popular fonts, then explore:

**For ligature lovers**:

- **FiraCode Nerd Font** - Extensive ligatures, modern
- **JetBrains Mono Nerd Font** - Clean with good ligatures

**For no-ligature preference**:

- **Hack Nerd Font** - Clean, excellent readability
- **Source Code Pro Nerd Font** - Professional, Adobe quality

**For maximum code density**:

- **Iosevka Nerd Font** - Narrow, fits more code

**For macOS users**:

- **Meslo Nerd Font** - Based on macOS Menlo

**For fun/personality**:

- **Comic Code Nerd Font** - Comic sans style

See [Font Comparison](../reference/fonts/font-comparison.md) for detailed comparisons.

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

## Using font-sync for Testing

This dotfiles repository includes `font-sync` for systematic font testing:

```bash
# List available fonts
font-sync list

# Apply a font
font-sync apply "FiraCode Nerd Font Mono"

# Start testing and track progress
font-sync test

# After a week, mark your decision
font-sync like      # or: font-sync dislike

# View testing log
font-sync log
```

See [Font Testing Workflow](../workflows/font-testing.md) for the complete systematic testing approach.

## Next Steps

After installation:

1. Configure terminal to use the Nerd Font
2. Restart terminal to apply changes
3. Verify icons display correctly in neovim, tmux, yazi
4. Use `font-sync` to test and find favorites
5. Archive fonts you don't use

## Further Reading

- **[Font Testing Workflow](../workflows/font-testing.md)** - Systematic approach to finding favorites
- **[Nerd Fonts Explained](../reference/fonts/nerd-fonts-explained.md)** - Understanding Mono/Propo variants
- **[Font Comparison](../reference/fonts/font-comparison.md)** - Detailed comparison of popular fonts
- **[Terminal Fonts Guide](../reference/fonts/terminal-fonts-guide.md)** - Why monospace matters
