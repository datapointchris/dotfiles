# Ghostty Terminal Theme Manager

## Overview

The `ghostty-theme` script provides an interactive theme management system for Ghostty terminal with live preview capabilities. The script was designed to make theme switching effortless while integrating seamlessly with the aerospace window manager to prevent workspace disruption.

## Why This Exists

Ghostty comes with hundreds of built-in themes, but there wasn't a good way to preview and switch between them efficiently. The themes are compiled into the Ghostty binary, which initially seemed like it would prevent live previewing. However, by leveraging Ghostty's ability to load custom config files per instance, the script creates temporary preview windows that show actual theme colors—similar to how Telescope previews colorschemes in Neovim.

The script solves several specific pain points: avoiding the accumulation of commented theme lines in the config file, preventing aerospace from rearranging windows when previews open, and providing a simple way to cycle through favorite themes without manually editing configuration files.

## Core Functionality

### Interactive Selection

Running `ghostty-theme --select` launches an fzf interface that displays your favorite themes. The interface uses Ghostty itself to show theme information in the preview pane. While you navigate through themes with arrow keys, the preview panel updates to show instructions and theme details.

The real power comes from the live preview feature. Pressing **Ctrl+P** while browsing themes opens a new Ghostty window with that theme actually applied. This isn't a simulation—it's the real theme colors rendered in a temporary Ghostty instance. The preview window is configured to float in aerospace (via window rules), so it doesn't disrupt your current workspace layout. You can open multiple preview windows side-by-side to compare themes directly.

When you find a theme you like and press Enter, the script updates your Ghostty config by replacing the single `theme =` line. This approach is much simpler than the initial implementation, which tried to comment out old themes and insert new ones at specific locations. Now there's just one theme line, and it gets replaced. Clean and straightforward.

### Random Theme Selection

The `--random` flag picks a random theme from your favorites list and applies it immediately. This is particularly useful when you want to explore themes quickly without going through the interactive selector. You can run it multiple times to cycle through different themes, and since new Ghostty windows pick up the new theme automatically, you can see results immediately by opening a new tab or window.

### Theme Management

Your favorite themes are stored in `~/.config/ghostty/favorite-themes.txt`. The format is intentionally simple: one theme name per line, no special syntax or metadata. Comments starting with `#` are ignored, and empty lines are skipped. The script doesn't do any whitespace trimming or parsing magic—theme names must be written exactly as Ghostty expects them, with proper spacing and capitalization.

The config file maintains a single theme line with a comment above it explaining that only one theme should be set. When you apply a new theme, the script finds the existing `theme =` line and replaces it. If for some reason there isn't a theme line yet, it adds one at the top with the explanatory comment. This keeps the config file clean and avoids the accumulation of commented-out theme history.

## Aerospace Integration

One of the key design considerations was making preview windows work smoothly with aerospace. When you press Ctrl+P to preview a theme, you don't want aerospace to suddenly rearrange your entire workspace to tile in the new window. The solution uses aerospace's window detection rules to automatically float any Ghostty window with "THEME PREVIEW:" in its title.

The window rule in `aerospace.toml` looks for the specific app ID and title pattern, then applies floating layout automatically. This happens instantly when the window opens, so you never see the tiling behavior. When you close the preview window, your workspace remains exactly as it was. You can open multiple preview windows, compare themes side-by-side, and close them without any workspace disruption.

## Script Architecture

The script maintains a simple functional architecture with clear separation of concerns. Theme reading is handled separately from theme application, which is separate from the preview logic. The fzf integration uses the script itself for preview rendering by calling back into the script with the `--preview` flag. This eliminates complex shell function exports and makes the preview system more reliable.

When you open a live preview window, the script creates a temporary config file with all your settings except it replaces the theme line with the preview theme. It then launches a new Ghostty instance with `open -na Ghostty.app` pointing to that temporary config. The preview window runs a bash session that displays the theme name, color samples using `printcolors`, and sample syntax-highlighted code. When you close the preview window, the cleanup is handled by the bash session's exit, which removes the temporary config file.

## Configuration Files

### Favorite Themes List

Located at `~/.config/ghostty/favorite-themes.txt`, this file contains your curated list of preferred themes:

```text
# Ghostty Favorite Themes
# One theme name per line (comments starting with # are ignored)

Black Metal (Mayhem)
Broadcast
Everforest Dark Hard
Material Design Colors
Rose Pine
Tomorrow Night Bright
```

Theme names must match exactly what Ghostty expects, including spaces and capitalization. You can find available themes by running `ghostty +list-themes`.

### Ghostty Config

Your main Ghostty config at `~/.config/ghostty/config` maintains a single theme line:

```text
# Theme (only one theme line should be set)
theme = Rose Pine

macos-titlebar-style = hidden
window-padding-x = 16
# ... rest of config
```

The comment serves as a reminder about the design choice to keep only one theme active. When you switch themes, that line gets replaced in place.

### Aerospace Window Rules

The floating window rule in `~/.config/aerospace/aerospace.toml`:

```toml
[[on-window-detected]]
if.app-id = 'com.mitchellh.ghostty'
if.window-title-regex-substring = 'THEME PREVIEW:'
run = 'layout floating'
```

This ensures preview windows float automatically without disrupting your tiled layout.

## Usage Examples

### Interactive Theme Selection

```bash
ghostty-theme --select
```

This opens the fzf selector where you can browse your favorite themes. Use arrow keys to navigate, Ctrl+P to preview any theme in a new window, and Enter to apply the selected theme.

### Quick Random Testing

```bash
ghostty-theme --random
```

Applies a random theme from your favorites. Great for exploring themes quickly or adding some variety to your terminal setup.

### Listing Favorites

```bash
ghostty-theme --list
```

Shows all themes in your favorites list with numbering.

### Checking Current Theme

```bash
ghostty-theme --current
```

Displays which theme is currently active in your config.

## Workflow Recommendations

The recommended workflow for finding and switching themes involves using the live preview feature liberally. When you're browsing themes in the selector, press Ctrl+P on anything that looks interesting. Since the preview windows float, you can open several at once and arrange them to compare themes side-by-side. The preview windows show the actual theme colors, not just a description, so you can see exactly how syntax highlighting, color contrast, and visual aesthetics will look.

Once you've narrowed down to a favorite, apply it with Enter. The theme gets written to your config immediately. To see it in action, press **Cmd+Shift+,** in any Ghostty window to reload the configuration. New windows and tabs will use the new theme instantly, while existing windows update after the config reload.

For maintaining your favorites list, keep it relatively small (10-20 themes) with themes you actually use. This makes the selector more useful since you're not scrolling through hundreds of options. You can always add themes from Ghostty's full catalog by editing the favorites file—just make sure to get the name exactly right by checking `ghostty +list-themes`.

## Technical Details

### Theme Application Logic

The script resolves symlinks when modifying the config file to ensure it writes to the actual file rather than trying to modify the symlink itself. This is important for the dotfiles setup where configs are symlinked from the repository. The resolution uses `readlink -f` or falls back to `realpath` for compatibility.

The theme replacement uses a simple sed substitution to find and replace the `theme =` line. If no theme line exists, it prepends one to the beginning of the file with the explanatory comment. This approach is significantly simpler than the original implementation and has proven more reliable.

### Preview Window Design

Preview windows are spawned as independent Ghostty instances with custom config files. The window title is specifically crafted to include "THEME PREVIEW:" which triggers the aerospace floating rule. The bash session inside the preview displays formatted output with color samples and instructions, then waits for user input before cleaning up.

The preview implementation took inspiration from how Telescope handles colorscheme previews in Neovim—by actually applying the theme in a separate context rather than trying to simulate what it would look like.

## Future Enhancements

Potential improvements could include adding theme metadata (like which themes work best for light vs dark backgrounds), implementing a recently-used themes feature, or creating theme collections for different contexts (work, evening coding, presentations). The architecture is flexible enough to support these additions without major refactoring.

Another useful enhancement would be integrating with the system appearance to automatically switch themes based on macOS dark mode state, though this would require additional scripting and system event monitoring.
