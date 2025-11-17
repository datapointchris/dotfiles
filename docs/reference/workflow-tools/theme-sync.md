# Theme Sync

Theme sync manages Base16 color schemes across multiple applications using tinty. Change your theme once and watch it apply to tmux, bat, fzf, eza, and your shell simultaneously. No more manually updating configs in different locations.

## Why Theme Sync Exists

Visual consistency matters for focus. When your terminal, editor, file viewer, and fuzzy finder use different color schemes, the visual noise is distracting. Switching themes should update everything at once, not require editing multiple config files.

Base16 provides a standard color scheme format. Tinty applies Base16 themes to various applications. Theme sync wraps tinty with convenient commands and manages a curated list of favorite themes. It handles reloading running applications so changes appear immediately.

This works alongside ghostty-theme for terminal-specific theme management. Use ghostty-theme for Ghostty, use theme-sync for everything else. The two systems complement each other.

## Quick Start

Check your current theme, apply a new one, or pick randomly from favorites:

```bash
theme-sync current       # Show current theme
theme-sync apply base16-rose-pine
theme-sync favorites     # List 12 favorite themes
theme-sync random        # Apply random favorite
```

Changes apply immediately to all running applications. Tmux reloads automatically. Bat rebuilds its cache. The shell picks up new colors.

## Commands

### Show Current Theme

See which theme is currently active:

```bash
theme-sync current
```

Shows the theme name from tinty's current scheme file. If no theme is applied, tells you that too.

### Apply Theme

Switch to a specific Base16 theme:

```bash
theme-sync apply base16-rose-pine
theme-sync apply base16-gruvbox-dark-hard
```

Theme sync applies the theme via tinty, then reloads running applications automatically. Tmux sources its config to pick up new colors. Bat rebuilds its cache to update syntax highlighting themes. No manual reloading required.

If the theme doesn't exist, you'll see an error suggesting you check available themes with `theme-sync list`.

### List All Themes

See every available Base16 theme:

```bash
theme-sync list
```

This shows all themes tinty knows about. The list is long - hundreds of themes. Use favorites to narrow it down to your preferred options.

### Show Favorites

See your curated list of 12 favorite themes:

```bash
theme-sync favorites
```

Shows:

```text
base16-rose-pine
base16-rose-pine-moon
base16-gruvbox-dark-hard
base16-gruvbox-dark-medium
base16-kanagawa
base16-oceanicnext
base16-github-dark
base16-nord
base16-selenized-dark
base16-everforest-dark-hard
base16-tomorrow-night
base16-tomorrow-night-eighties
```

These favorites match the themes configured in Neovim and Ghostty for consistency. Pick from this list instead of browsing hundreds of options.

### Show Theme Info

See the color palette for a specific theme:

```bash
theme-sync info base16-rose-pine
```

Displays the full color scheme with hex values. Useful for checking if a theme matches your expectations before applying it.

### Apply Random Theme

Pick and apply a random theme from favorites:

```bash
theme-sync random
```

Shows which theme it selected, then applies it. Perfect for breaking out of visual monotony or discovering themes you forgot about.

### Reload Applications

Reload theme in running applications without changing the theme:

```bash
theme-sync reload
```

Useful if you manually edited theme configs and want running applications to pick up changes.

### Verify System

Check that the theme system is working correctly:

```bash
theme-sync verify
```

Verifies:

- Tinty is installed
- Config file exists
- Current theme is set
- Tmux theme file exists
- Bat themes directory exists

Shows checkmarks for working components and warnings for missing pieces. Run this if themes aren't applying correctly.

## Favorite Themes

The 12 favorite themes balance variety with quality:

**Rose Pine family** - Warm, comfortable, low-contrast themes perfect for long coding sessions:

- base16-rose-pine
- base16-rose-pine-moon

**Gruvbox family** - High-contrast retro themes that are easy on the eyes:

- base16-gruvbox-dark-hard
- base16-gruvbox-dark-medium

**Modern favorites** - Contemporary themes with excellent syntax highlighting:

- base16-kanagawa (Japanese-inspired, warm and earthy)
- base16-oceanicnext (cool blues, professional)
- base16-github-dark (familiar GitHub colors)
- base16-nord (arctic, frosty blues)

**Specialized options**:

- base16-selenized-dark (scientifically balanced contrast)
- base16-everforest-dark-hard (forest greens, comfortable)
- base16-tomorrow-night (classic, neutral)
- base16-tomorrow-night-eighties (nostalgic pastels)

These themes are curated to work well across all tools - tmux, bat, fzf, Neovim. They're tested and known to be readable.

## How It Works

Theme sync uses tinty as its engine. Tinty applies Base16 themes by generating config files for each application. When you apply a theme, tinty writes new config files and theme-sync reloads the affected applications.

### Application Integration

**Tmux** sources `~/.config/tmux/themes/current.conf` which tinty generates. Theme-sync reloads tmux config automatically after applying themes.

**Bat** uses themes from its themes directory. Theme-sync rebuilds bat's cache after applying themes so syntax highlighting updates immediately.

**Fzf** sources theme variables from shell environment. New shells pick up theme changes automatically.

**Eza** (ls replacement) uses LS_COLORS which tinty updates. New commands see new colors.

**Shell** sources theme variables that tinty exports. Your prompt and other shell colors update.

### Tinty Configuration

Tinty reads `~/.config/tinty/config.toml` which defines where to write theme files:

```toml
[[items]]
path = "https://github.com/tinted-theming/base16-schemes"
name = "base16"

[[items]]
path = "https://github.com/tinted-theming/base24-schemes"
name = "base24"
```

This tells tinty where to download Base16 schemes. Theme-sync doesn't modify tinty's config - it uses tinty as-is.

## Integration with Ghostty

Theme-sync works alongside the separate ghostty-theme script. Why two theme systems?

Ghostty uses its own theme format and config system. Ghostty-theme manages Ghostty's 60+ built-in themes separately from Base16. This lets you switch Ghostty themes independently from other tools.

Use both systems together:

```bash
ghostty-theme current          # Check Ghostty theme
theme-sync current             # Check Base16 theme across other tools
```

Or keep them synchronized by applying matching themes:

```bash
ghostty-theme apply rose-pine
theme-sync apply base16-rose-pine
```

The separation provides flexibility. Sometimes you want everything matching. Sometimes you want your terminal different from your editor.

## Configuration

Theme-sync has minimal configuration. Favorite themes are hardcoded in the script at `apps/common/theme-sync`. Edit this file to change your favorites:

```bash
FAVORITES=(
  "base16-rose-pine"
  "base16-rose-pine-moon"
  # ... more themes
)
```

Tinty configuration lives at `~/.config/tinty/config.toml` and defines theme repositories and application integrations.

## Common Workflows

### Daily Theme Changes

Switch themes based on mood or time of day:

```bash
theme-sync apply base16-rose-pine-moon    # Evening
theme-sync apply base16-github-dark       # Daytime
```

### Exploring Themes

Try random favorites until something feels right:

```bash
theme-sync random
# Work for a bit, see how it feels
theme-sync random
# Try another
```

### Matching Terminal

Coordinate with Ghostty theme:

```bash
ghostty-theme apply rose-pine
theme-sync apply base16-rose-pine
```

### Interactive Selection

Combine with fzf for interactive theme picking:

```bash
theme-sync favorites | fzf | xargs theme-sync apply
```

Select from favorites visually, apply when you press Enter.

## Troubleshooting

### Theme Not Applying

If themes don't apply:

- Run `theme-sync verify` to check system status
- Verify tinty is installed: `which tinty`
- Check tinty config exists: `ls ~/.config/tinty/config.toml`
- Try applying theme manually: `tinty apply base16-rose-pine`

### Tmux Not Updating

If tmux doesn't pick up new colors:

- Check tmux theme file exists: `ls ~/.config/tmux/themes/current.conf`
- Manually reload tmux: `tmux source-file ~/.config/tmux/tmux.conf`
- Verify tmux is running: `tmux info`

### Bat Not Updating

If bat syntax highlighting doesn't change:

- Rebuild cache manually: `bat cache --build`
- Check bat themes directory: `ls $(bat --config-dir)/themes`
- Verify bat picks up themes: `bat --list-themes | grep base16`

### Theme Doesn't Exist

If you get "theme not found" errors:

- Run `theme-sync list` to see available themes
- Check exact theme name (case-sensitive)
- Ensure tinty has downloaded schemes: `tinty list`
- Update tinty schemes: `tinty update`

### Colors Look Wrong

If colors appear incorrect:

- Check terminal supports 256 colors: `tput colors`
- Verify TERM variable: `echo $TERM`
- Try different theme to rule out theme-specific issues
- Check tinty generated correct config: `cat ~/.config/tmux/themes/current.conf`

## Advanced Usage

### Time-Based Theme Switching

Script theme changes based on time of day:

```bash
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply base16-github-dark
else
  theme-sync apply base16-rose-pine
fi
```

Add to crontab or shell startup to automate theme changes.

### Theme Testing

Preview themes quickly:

```bash
for theme in $(theme-sync favorites); do
  echo "Testing: $theme"
  theme-sync apply "$theme"
  sleep 5
done
```

Cycles through favorites with 5-second pauses. See each theme in context.

### Custom Favorites

Edit the theme-sync script to customize favorites:

```bash
nvim ~/dotfiles/apps/common/theme-sync
# Edit FAVORITES array
# Save and changes apply immediately
```

No compilation or installation needed - shell scripts run directly.

## See Also

- [Ghostty Theme Management](/configuration/ghostty.md) - Terminal-specific themes
- [Tmux Configuration](/configuration/tmux.md) - Tmux color customization
- [Neovim Themes](/configuration/neovim.md) - Editor theme configuration
- [Tool Discovery](toolbox.md) - Finding installed tools
