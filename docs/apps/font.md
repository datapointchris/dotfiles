---
icon: material/format-font
---

# Font Tool

Font testing and management with data-driven rankings — every apply, like, dislike, or note is logged, and rankings emerge from your real usage. A standalone project: **[datapointchris/font](https://github.com/datapointchris/font)** is the source of truth for the full command reference, data model, and sync.

## In this system

- **Install** — custom installer (`install/common/custom-installers/font.sh`): git clone to `~/.local/share/font`, symlink into `~/.local/bin`. Update with `font update`.
- **Applies to dotfiles-managed apps** — `font apply` sets the font for Ghostty and Neovim (the configs this repo deploys) in one step and auto-logs the change.
- **Data** — per-platform history in `~/.config/font/` (`history-<platform>.jsonl` plus rejection files); cross-machine sync via GitHub Gist. Each platform writes only its own files, so there are no merge conflicts.

## See Also

- [Nerd Fonts Explained](https://docs.ichrisbirch.com/fonts/nerd-fonts-explained/) — what Nerd Fonts are and why they matter
- [Font Weights and Variants](https://docs.ichrisbirch.com/fonts/font-weights-and-variants/) — understanding Bold/Italic/Light variants
- [Terminal Fonts Guide](https://docs.ichrisbirch.com/fonts/terminal-fonts-guide/) — why monospace matters for terminals
- [Font Comparison](https://docs.ichrisbirch.com/fonts/font-comparison/) — detailed comparison of font families
