# Theme Customization Workflows

Theme customization provides visual consistency across the development environment. Change the theme once and watch it propagate to tmux, bat, fzf, eza, and the shell simultaneously. No manual config editing, no inconsistent colors between tools, no visual noise breaking focus.

## Exploring Available Themes

Start by checking the current theme to understand the baseline. This shows what's active across all integrated applications.

```bash
theme-sync current
```

Browse the curated list of 12 favorite themes instead of sifting through hundreds of options. These favorites balance variety with quality and work well across all tools.

```bash
theme-sync favorites
```

The favorites include warm, comfortable themes like Rose Pine for long coding sessions. High-contrast retro themes like Gruvbox that are easy on the eyes. Modern themes like Kanagawa and Oceanic Next with excellent syntax highlighting. Classic themes like Nord and Tomorrow Night for familiar, professional looks.

Each theme has been tested across tmux, bat, fzf, and Neovim to ensure readability and visual coherence. The curated list removes decision paralysis while providing enough variety to match different moods and contexts.

## Applying Themes Interactively

Change themes with immediate feedback. Apply a theme and see it update everywhere at once.

```bash
theme-sync apply base16-rose-pine
```

The apply command triggers tinty to generate new config files for each application, then automatically reloads running applications. Tmux sources its config to pick up new colors. Bat rebuilds its cache to update syntax highlighting. New shells pick up updated environment variables. The change propagates without manual intervention.

Try themes quickly to see how they feel in context. Some themes look good in screenshots but strain the eyes during actual work. Some themes work better for certain tasks - high contrast for detailed code review, softer themes for long writing sessions.

```bash
theme-sync apply base16-gruvbox-dark-hard
# Work for a bit, see how it feels
theme-sync apply base16-nord
# Try another
```

## Command Line Theme Selection

For workflow automation or quick switches, apply themes directly by name. This enables scripting theme changes based on time of day, project context, or other conditions.

```bash
theme-sync apply base16-rose-pine-moon    # Evening work
theme-sync apply base16-github-dark       # Daytime work
```

Combine with shell conditionals to automate theme selection based on the current hour. Add to shell startup files or crontab to make theme changes automatic.

```bash
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply base16-github-dark
else
  theme-sync apply base16-rose-pine
fi
```

Light themes during daylight hours reduce eye strain in bright environments. Dark themes in the evening maintain comfort during extended work sessions. Automation removes the need to remember to switch manually.

## Setting Favorite Themes

The default favorites provide a solid starting point, but personal preferences vary. Customize the favorites list to match preferred themes.

Edit the theme-sync script directly to modify the favorites array:

```bash
nvim ~/dotfiles/apps/common/theme-sync
```

Locate the FAVORITES array near the top of the script and modify the theme names. Changes apply immediately since shell scripts run directly - no compilation or installation needed.

```bash
FAVORITES=(
  "base16-rose-pine"
  "base16-custom-theme"
  "base16-another-favorite"
  # ... more themes
)
```

Keep the list manageable. Too many favorites defeats the purpose of curation. Aim for 8-15 themes that serve different purposes - some for focus, some for comfort, some for variety.

## Random Theme Selection

Break out of visual monotony by applying random themes from favorites. This helps rediscover forgotten themes and adds variety to the environment.

```bash
theme-sync random
```

The random command picks from favorites only, not from all available themes. This ensures a reasonable baseline quality while still providing surprise. Run it when the current theme feels stale or when starting a new context.

Incorporate random theme selection into daily routines. Apply a random theme each morning for variety. Use it when starting different types of work to create mental context shifts.

## Integrating with Ghostty

Theme-sync works alongside the separate ghostty-theme system. Ghostty uses its own theme format and manages its 60+ built-in themes independently from Base16. This separation provides flexibility.

Keep terminal and tool themes synchronized for complete visual coherence:

```bash
ghostty-theme apply rose-pine
theme-sync apply base16-rose-pine
```

Or intentionally separate them for visual distinction. Run a light terminal theme with dark tmux panes to create clear boundaries between different workspace types. Use different themes to distinguish between local terminal and remote SSH sessions.

```bash
ghostty-theme current          # Check Ghostty theme
theme-sync current             # Check Base16 theme for other tools
```

The two systems coexist peacefully. Use both for complete theme control, use just theme-sync if not using Ghostty, use just ghostty-theme for terminal-only changes.

## Interactive Theme Selection with FZF

Combine theme-sync with fzf for visual theme browsing. Select from favorites with a preview interface.

```bash
theme-sync favorites | fzf | xargs theme-sync apply
```

This pipeline lists favorites, presents them in fzf for selection, then applies the chosen theme. Extend this pattern with custom scripts to preview theme palettes before applying.

Build more complex selection interfaces that show theme information during browsing:

```bash
theme-sync favorites | fzf --preview 'theme-sync info {}' | xargs theme-sync apply
```

The preview shows the full color palette for each theme, making informed choices easier without applying and unapplying repeatedly.

## Time-Based Theme Switching

Automate theme changes based on time of day to match environment lighting. Bright themes during daylight, comfortable dark themes in the evening and early morning.

Create a script that checks the current hour and applies appropriate themes:

```bash
#!/usr/bin/env bash
hour=$(date +%H)

if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply base16-github-dark
else
  theme-sync apply base16-rose-pine
fi
```

Add this to crontab to run every hour, or source it in shell startup files to check on each new shell. The theme adapts to changing lighting conditions automatically.

Extend the pattern with multiple time ranges for more nuanced control. Morning themes, afternoon themes, evening themes, and late night themes all serve different lighting contexts and energy levels.

## Theme Testing Workflow

Preview themes systematically before settling on favorites. Cycle through candidates with timed pauses to see each theme in actual work context.

```bash
for theme in $(theme-sync favorites); do
  echo "Testing: $theme"
  theme-sync apply "$theme"
  sleep 5
done
```

Work with each theme long enough to see how it handles actual code, not just how it looks at first glance. Some themes appear attractive initially but cause eye strain after extended use. Others look plain but prove remarkably comfortable during long sessions.

Test themes during different tasks - writing code, reading documentation, reviewing diffs, editing configuration files. A theme that works well for Python might struggle with JSON or shell scripts. Comprehensive testing reveals these differences.

## Troubleshooting Theme Changes

When themes don't apply correctly, the issue usually involves missing dependencies or configuration problems. Run the verify command to check system status.

```bash
theme-sync verify
```

This checks that tinty is installed, config files exist, the current theme is set, and application-specific theme files are present. Checkmarks indicate working components, warnings point to missing pieces.

If tmux doesn't pick up new colors, manually reload the configuration to verify theme files are correct:

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

If bat syntax highlighting doesn't change, rebuild the cache manually:

```bash
bat cache --build
```

Check that tinty has the theme downloaded. Sometimes theme repositories need updating:

```bash
tinty list                # See available themes
tinty update              # Update theme repositories
```

## Custom Theme Development

For complete control over color schemes, create custom Base16 themes. Base16 uses a 16-color palette defined in YAML format.

Create a new theme file in tinty's scheme directory following the Base16 template format. The file defines colors for background, foreground, and 14 accent colors. Tinty generates application configs from this single source.

Custom themes integrate seamlessly with theme-sync. Add custom theme names to the favorites array. Apply them like any other theme. This workflow supports highly personalized color schemes while maintaining consistency across tools.

## Application-Specific Considerations

Theme-sync applies themes universally, but individual applications may need additional configuration for optimal results.

Tmux picks up colors from `~/.config/tmux/themes/current.conf` which tinty generates. The tmux config sources this file, making theme changes automatic. Verify the source line exists in `tmux.conf` for themes to work.

Bat uses themes from its themes directory. Theme-sync rebuilds bat's cache after applying themes, but custom bat themes require manual cache rebuilding. Use `bat cache --build` after adding custom themes.

Fzf sources theme variables from shell environment. New shells pick up theme changes automatically, but existing shells need to re-source the environment file or restart to see changes.

## See Also

- [Theme Sync Reference](../reference/workflow-tools/theme-sync.md) - Complete theme-sync command reference
- [Tool Discovery](../reference/workflow-tools/toolbox.md) - Finding installed tools
- [Session Management](sessions.md) - Related workflow for managing sessions
