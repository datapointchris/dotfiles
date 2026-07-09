---
icon: material/palette
---

# Theme Tool

Unified theme management — one command applies a consistent color scheme across your terminals, status bars, and editor. A standalone project: **[datapointchris/theme](https://github.com/datapointchris/theme)** is the source of truth for commands, the theme catalog, the `theme.yml` schema, and how to author new themes.

## In this system

- **Install** — custom installer (`install/common/custom-installers/theme.sh`): git clone to `~/.local/share/theme`, symlink into `~/.local/bin`. Update with `theme upgrade`.
- **Writes into dotfiles-managed configs** — `theme apply` regenerates the Ghostty, Kitty, tmux, btop, and (per platform) Hyprland / Waybar / Dunst / Rofi config files this repo deploys, so one command re-themes every app at once.
- **Neovim integration** — `colorscheme-manager.lua` in this repo's Neovim config watches `~/.local/state/theme/current` and switches colorscheme on `theme apply`; rejected themes are filtered from the `<leader>fz` picker.
- **Data** — history and rejections live in `~/.config/theme/` (per-platform files; cross-machine sync via GitHub Gist).

## See Also

- [Font Tool](font.md) — companion font management
- [Shell Libraries](../architecture/shell-libraries.md) — formatting library the tool uses
