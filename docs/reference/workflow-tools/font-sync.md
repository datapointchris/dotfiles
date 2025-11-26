# font-sync

Systematic font testing and management tool for finding and maintaining favorite coding fonts.

## Overview

`font-sync` provides a structured workflow for testing fonts over time, tracking preferences, and building a curated collection. Modeled after theme-sync, it eliminates decision paralysis by enabling systematic evaluation and random selection.

## Quick Start

```bash
font-sync preview         # Interactive font picker
font-sync adventure      # Apply random font and start testing
font-sync test           # Start tracking current font test
font-sync like           # Mark current font as keeper
font-sync log            # View testing history
```text

## Commands

### list

List all available Nerd Fonts installed on the system.

```bash
font-sync list
```

Searches installed fonts for Nerd Fonts and coding fonts, displaying unique family names sorted alphabetically.

### favorites

Show curated list of favorite fonts.

```bash
font-sync favorites
```text

Displays fonts in the FAVORITES array defined in the script. Edit favorites by modifying the script directly.

### current

Display currently active font from Ghostty configuration.

```bash
font-sync current
```

Reads `~/.config/ghostty/config` and extracts the font-family setting.

### apply

Apply a font to Ghostty and Neovim configurations.

```bash
font-sync apply "FiraCode Nerd Font Mono"
```text

Updates:

- Ghostty config: `font-family` setting
- Neovim config: `guifont` setting (if file exists)
- Creates .bak backups before modifying

Restart Ghostty to see changes take effect.

### test

Start tracking a font test with timestamp.

```bash
font-sync test "JetBrains Mono Nerd Font"
# or
font-sync test  # Uses current font
```

Records in testing log:

- Updates "Currently Testing" section with font name and start date
- Adds entry to testing history

Use this when beginning systematic font evaluation.

### like

Mark font as a keeper.

```bash
font-sync like "FiraCode Nerd Font"
# or
font-sync like  # Uses current font
```text

Records in testing log:

- Adds to "Liked (Keepers)" section with date
- Clears from "Currently Testing" section

Use after deciding a font works well and should be kept.

### dislike

Mark font for removal.

```bash
font-sync dislike "Source Code Pro"
# or
font-sync dislike  # Uses current font
```

Records in testing log:

- Adds to "Disliked (Can Remove)" section with date
- Clears from "Currently Testing" section

Use after deciding a font doesn't work and can be deleted.

### notes

Add observations about a font.

```bash
font-sync notes "FiraCode Nerd Font" "Great ligatures but too narrow for extended use"
```text

Appends notes with timestamp to testing log. Useful for recording specific observations about readability, comfort, or use cases.

### log

View the testing log.

```bash
font-sync log
```

Displays the font testing log using `bat` (if installed) or `cat`. Log tracks:

- Currently testing font
- Liked fonts (keepers)
- Disliked fonts (candidates for removal)
- Testing history with dates
- Notes and observations

### preview

Interactive font selection with fzf.

```bash
font-sync preview
```text

Opens fzf with:

- List of all available fonts
- Preview showing character samples
- Applies selected font immediately

Requires fzf to be installed.

### random

Apply random font from favorites.

```bash
font-sync random
```

Selects random font from FAVORITES array and applies it. Useful for rotation without decision fatigue.

Safe choice - only picks from curated favorites.

### adventure

Apply random font from ALL available fonts.

```bash
font-sync adventure
```text

Selects random font from all installed fonts and:

- Applies it immediately
- Starts tracking the test automatically
- Displays "adventure mode" message

Use this to avoid decision paralysis - let randomness choose, then evaluate during actual use. Mirrors the theme-sync random workflow.

### install

Install font file from code_fonts directory to system.

```bash
font-sync install "FiraCode-Regular.otf"
```

Copies font file from `~/Documents/code_fonts/` to `~/Library/Fonts/`. Run `fc-cache -f` after installation to refresh font cache.

## Configuration

Font testing log location (XDG-compliant):

```text
~/.local/share/font-sync/font-testing-log.md
```

Favorites list location:

```text
~/dotfiles/apps/common/font-sync
# Edit FAVORITES array in the script
```

Config files updated:

```text
~/.config/ghostty/config         # font-family setting
~/.config/nvim/lua/config/font.lua  # guifont setting (if exists)
```

## Favorites Management

Edit favorites by modifying the script:

```bash
nvim ~/dotfiles/apps/common/font-sync
```text

Update the FAVORITES array:

```bash
FAVORITES=(
  "SeriousShanns Nerd Font Propo"
  "FiraCode Nerd Font Mono"
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
```text

## Workflow Integration

### Weekly Testing Cycle

```bash
# Monday morning
font-sync adventure  # or: font-sync preview

# Work all week with the font
# Use it for actual coding, not just looking at it

# Friday afternoon
font-sync like    # or: font-sync dislike

# Start new font next Monday
```

### Quick Rotation

```bash
# Rotate through favorites without decision fatigue
font-sync random
```text

### Review Progress

```bash
# See what's been tested and decisions made
font-sync log

# Check current font
font-sync current
```

## Examples

### Start systematic testing

```bash
# Pick a font interactively
font-sync preview

# Start tracking the test
font-sync test
```text

### Let randomness decide

```bash
# Adventure mode - random from all fonts
font-sync adventure
# (automatically starts tracking)
```

### Record a decision

```bash
# After a week of use
font-sync like

# Add specific notes
font-sync notes "FiraCode Nerd Font" "Ligatures excellent for JS/TS, too busy for Python"
```text

### View testing history

```bash
font-sync log
```

## Integration with Ghostty

Font changes in Ghostty require terminal restart. After `font-sync apply`:

1. Save current terminal session (if needed)
2. Quit Ghostty completely
3. Restart Ghostty
4. Font change now visible

For quick testing without restarting, use Neovim's `guifont` if testing in GUI Neovim.

## Integration with Neovim

If `~/.config/nvim/lua/config/font.lua` exists, `font-sync` updates:

```lua
vim.o.guifont = "FontName:h15"
```text

Restart Neovim or reload config to see changes.

## Troubleshooting

**Font doesn't appear in list**:

- Check if installed: `fc-list | grep "FontName"`
- Ensure it's a Nerd Font variant
- Run `fc-cache -f` to refresh cache

**Apply doesn't work**:

- Check Ghostty config exists at `~/.config/ghostty/config`
- Verify font name matches installed name exactly
- Restart Ghostty after applying

**Random always picks same font**:

- Shell RANDOM is deterministic with same seed
- Run multiple times or restart shell

**Notes command fails**:

- Ensure font name is in quotes
- Use `--` before notes if they start with `-`

## Related Tools

- **theme-sync** - Similar workflow for color themes
- **ghostty-theme** - Ghostty-specific theme management

## See Also

- [Font Testing Workflow](../../workflows/font-testing.md) - Complete testing methodology
- [Font Comparison](../fonts/font-comparison.md) - Detailed font comparisons
- [Theme Sync Reference](theme-sync.md) - Similar tool for themes
