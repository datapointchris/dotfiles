# font

Systematic font testing and management tool for finding and maintaining favorite coding fonts.

## Overview

`font` provides a structured workflow for testing fonts over time, tracking preferences, and building a curated collection. Modeled after theme-sync, it eliminates decision paralysis by enabling systematic evaluation and random selection.

## Application Structure

The font application follows a modular, testable architecture:

```
~/dotfiles/apps/common/font/
├── bin/
│   └── font              # Main executable (symlinked to ~/.local/bin/font)
├── commands/
│   ├── cleanup           # Font cleanup utilities
│   ├── download          # Font download automation
│   ├── hoard             # Font hoarding/collection management
│   └── install           # Font installation to system
├── data/
│   └── preview-text.txt  # Sample code for preview generation
├── lib/
│   └── lib.sh            # Core library functions
└── tests/
    └── test              # Comprehensive test suite (120+ tests)
```

**Key design principles:**

- Modular library with single-responsibility functions
- Comprehensive test coverage for all core functionality
- XDG-compliant data storage
- Platform-aware font installation (macOS, Linux, WSL)

## Quick Start

```bash
font preview         # Interactive font picker
font adventure       # Apply random font and start testing
font test            # Start tracking current font test
font like            # Mark current font as keeper
font log             # View testing history
```

## Commands

### list

List all available coding fonts installed on the system.

```bash
font list
```

Searches installed fonts for Nerd Fonts and coding fonts, displaying unique family names sorted alphabetically. Aggressively filters out style variations (Bold, Italic, Light, etc.) to show only main font families.

### favorites

Show curated list of favorite fonts.

```bash
font favorites
```

Displays fonts in the FAVORITES array defined in the script. Edit favorites by modifying the script directly.

### current

Display currently active font from Ghostty configuration.

```bash
font current
```

Reads `~/.config/ghostty/config` and extracts the font-family setting.

### apply

Apply a font to Ghostty and Neovim configurations.

```bash
font apply "FiraCode Nerd Font"
```

Updates:

- Ghostty config: `font-family` setting
- Neovim config: `guifont` setting (if file exists)
- Creates .bak backups before modifying

Restart Ghostty to see changes take effect.

### test

Start tracking a font test with timestamp.

```bash
font test "JetBrains Mono Nerd Font"
# or
font test  # Uses current font
```

Records in testing log:

- Updates "Currently Testing" section with font name and start date
- Adds entry to testing history

Use this when beginning systematic font evaluation.

### like

Mark font as a keeper.

```bash
font like "FiraCode Nerd Font"
# or
font like  # Uses current font
```

Records in testing log:

- Adds to "Liked (Keepers)" section with date
- Clears from "Currently Testing" section

Use after deciding a font works well and should be kept.

### dislike

Mark font for removal.

```bash
font dislike "Source Code Pro"
# or
font dislike  # Uses current font
```

Records in testing log:

- Adds to "Disliked (Can Remove)" section with date
- Clears from "Currently Testing" section

Use after deciding a font doesn't work and can be deleted.

### notes

Add observations about a font.

```bash
font notes "FiraCode Nerd Font" "Great ligatures but too narrow for extended use"
```

Appends notes with timestamp to testing log. Useful for recording specific observations about readability, comfort, or use cases.

### log

View the testing log.

```bash
font log
```

Displays the font testing log using `bat` (if installed) or `cat`. Log tracks:

- Currently testing font
- Liked fonts (keepers)
- Disliked fonts (candidates for removal)
- Testing history with dates
- Notes and observations

### preview

Interactive font selection with fzf and visual font preview.

```bash
font preview
```

Opens fzf with:

- List of all available fonts
- Real visual preview of each font (rendered as image)
- Preview shows comprehensive code samples:
  - Character differentiation (0O, 1lI, etc.)
  - Python with type hints, decorators, list comprehensions
  - Go with interfaces, concurrency, error handling
  - Rust with pattern matching, ownership, lifetimes
  - Bash with arrays, parameter expansion, conditionals
- Preview cached in `/tmp/font-preview/` for performance
- Applies selected font immediately

Requires:

- `fzf` - Interactive fuzzy finder
- `imagemagick` - For generating font preview images
- `chafa` or `viu` - For image display using Kitty graphics protocol (works in Ghostty and Kitty terminals)

Install image viewer:

```bash
brew install chafa  # Recommended
# or
brew install viu    # Alternative
```

If neither is installed, falls back to text-based preview.

### random

Apply random font from favorites.

```bash
font random
```

Selects random font from FAVORITES array and applies it. Useful for rotation without decision fatigue.

Safe choice - only picks from curated favorites.

### adventure

Apply random font from ALL available fonts.

```bash
font adventure
```

Selects random font from all installed fonts and:

- Applies it immediately
- Starts tracking the test automatically
- Displays "adventure mode" message

Use this to avoid decision paralysis - let randomness choose, then evaluate during actual use. Mirrors the theme-sync random workflow.

### generate-previews

Pre-generate all font preview images for instant browsing.

```bash
font generate-previews
```

Generates preview images for all available fonts and caches them in `/tmp/font-preview/`. This makes the interactive preview instant instead of generating images on-demand.

Useful for:

- First-time setup
- After installing new fonts
- After clearing preview cache

### clear-cache

Clear the preview image cache.

```bash
font clear-cache
```

Removes all cached preview images from `/tmp/font-preview/`. Use this to force regeneration of previews (e.g., after updating preview text or changing preview settings).

## Configuration

### Font Testing Log Location

XDG-compliant data location:

```text
~/.local/share/font/font-testing-log.md
```

In dotfiles repository:

```text
platforms/common/.local/share/font/
```

This directory is symlinked to `~/.local/share/font/` by the dotfiles symlink infrastructure, ensuring the log syncs across systems while remaining XDG compliant.

### Preview Cache

Temporary preview images cached at:

```text
/tmp/font-preview/
```

Cache is automatically created and persists during system session. Cleared on reboot.

### Favorites List

```text
~/dotfiles/apps/common/font/bin/font
# Edit FAVORITES array in the script
```

### Config Files Updated

```text
~/.config/ghostty/config              # font-family setting
~/.config/nvim/lua/config/font.lua    # guifont setting (if exists)
```

### Preview Text

```text
~/dotfiles/apps/common/font/data/preview-text.txt
```

Contains sample code used for generating preview images. Edit this file to customize what code samples are shown in previews.

## Favorites Management

Edit favorites by modifying the script:

```bash
nvim ~/dotfiles/apps/common/font/bin/font
```

Update the FAVORITES array:

```bash
FAVORITES=(
  "SeriousShanns Nerd Font Propo"
  "FiraCode Nerd Font"
  "JetBrains Mono Nerd Font"
  "Source Code Pro Nerd Font"
  # Add discovered favorites here
)
```

Changes take effect immediately (shell scripts run directly).

## Testing Log Format

The log uses markdown format:

```markdown
# Font Testing Log

## Currently Testing

JetBrains Mono Nerd Font (started 2025-01-15)

## Liked (Keepers)

- FiraCode Nerd Font - Added 2025-01-08
- SeriousShanns Nerd Font Propo - Added 2025-01-01

## Disliked (Can Remove)

- Comic Mono - Added 2025-01-10

## Testing History

- **JetBrains Mono Nerd Font** - Started 2025-01-15
- **Comic Mono** - Started 2025-01-08
```

## Workflow Integration

### Weekly Testing Cycle

```bash
# Monday morning
font adventure  # or: font preview

# Work all week with the font
# Use it for actual coding, not just looking at it

# Friday afternoon
font like    # or: font dislike

# Start new font next Monday
```

### Quick Rotation

```bash
# Rotate through favorites without decision fatigue
font random
```

### Review Progress

```bash
# See what's been tested and decisions made
font log

# Check current font
font current
```

## Examples

### Start systematic testing

```bash
# Pick a font interactively
font preview

# Start tracking the test
font test
```

### Let randomness decide

```bash
# Adventure mode - random from all fonts
font adventure
# (automatically starts tracking)
```

### Record a decision

```bash
# After a week of use
font like

# Add specific notes
font notes "FiraCode Nerd Font" "Ligatures excellent for JS/TS, too busy for Python"
```

### View testing history

```bash
font log
```

## Integration with Ghostty

Font changes in Ghostty require terminal restart. After `font apply`:

1. Save current terminal session (if needed)
2. Quit Ghostty completely
3. Restart Ghostty
4. Font change now visible

For quick testing without restarting, use Neovim's `guifont` if testing in GUI Neovim.

## Integration with Neovim

If `~/.config/nvim/lua/config/font.lua` exists, `font` updates:

```lua
vim.o.guifont = "FontName:h15"
```

Restart Neovim or reload config to see changes.

## Development

### Running Tests

```bash
~/dotfiles/apps/common/font/tests/test
```

Runs comprehensive test suite (120+ tests) covering:

- Font listing and filtering
- Font file path resolution
- Preview text file validation
- Preview image generation
- Cache functionality
- Display tool integration

### Library Functions

Core functionality is in `~/dotfiles/apps/common/font/lib/lib.sh`:

- `list_fonts()` - List main font families (filtered)
- `get_font_file_path()` - Get font file path by family name
- `generate_font_preview()` - Generate preview image
- `get_or_generate_preview()` - Get cached or generate new preview
- `validate_preview_image()` - Validate preview image file
- `display_preview_image()` - Display preview in terminal

All functions are independently testable and follow single-responsibility principle.

## Troubleshooting

**Font doesn't appear in list**:

- Check if installed: `fc-list | grep "FontName"`
- Ensure it's a Nerd Font or coding font variant
- Run `fc-cache -f` to refresh font cache

**Apply doesn't work**:

- Check Ghostty config exists at `~/.config/ghostty/config`
- Verify font name matches installed name exactly
- Restart Ghostty after applying

**Preview doesn't show images**:

- Ensure ImageMagick is installed: `brew install imagemagick`
- Install chafa or viu: `brew install chafa` (or `brew install viu`)
- Verify you're using Ghostty or Kitty terminal (both support Kitty graphics protocol)
- Check preview cache has write permissions: `ls -la /tmp/font-preview/`
- If chafa/viu not installed, text-based fallback will be used

**Preview shows "Failed to generate preview"**:

- Font name may not match system font database
- Check available fonts: `fc-list : family | grep "FontName"`
- Some fonts may require specific style selection

**Random always picks same font**:

- Shell RANDOM is deterministic with same seed
- Run multiple times or restart shell

**Notes command fails**:

- Ensure font name is in quotes
- Use `--` before notes if they start with `-`

**Testing log not syncing across systems**:

- Verify symlink exists: `ls -la ~/.local/share/font`
- Check dotfiles symlink infrastructure is set up
- Ensure `platforms/common/.local/share/font/` is tracked in git

## Related Tools

- **theme-sync** - Similar workflow for color themes
- **ghostty-theme** - Ghostty-specific theme management

## See Also

- [Font Testing Workflow](../../workflows/font-testing.md) - Complete testing methodology
- [Font Comparison](../fonts/font-comparison.md) - Detailed font comparisons
- [Theme Sync Reference](theme-sync.md) - Similar tool for themes
