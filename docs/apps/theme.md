---
icon: material/palette
---

# Theme and font

Two standalone projects, [datapointchris/theme](https://github.com/datapointchris/theme)
and [datapointchris/font](https://github.com/datapointchris/font). Each is the
source of truth for its own commands, catalog, data model and sync. Both reach a
machine through the custom-installer path in `src/dotfiles/providers/custom.py`,
which clones into `~/.local/share/<tool>` and symlinks the entry point into
`~/.local/bin`.

## Deployed configs point at `current`, never at a theme

Nothing this repo deploys names a theme or a font. Every config that gets themed
reads a stable `current` file that the tool rewrites in place, and the same holds
for fonts through `fonts/current`. Changing either therefore touches no file
here, which is why switching theme is not a commit.

List the configs holding a pointer with `rg -l --hidden '/current\b' configs/`.
The `--hidden` is load-bearing, since every one of them sits under a `.config`
directory that `rg` skips by default.

## Neovim is the one config that reads the tool's own state

`configs/common/.config/nvim/lua/plugins/colorscheme-manager.lua` loads generated
colorschemes straight out of the theme tool's checkout, rather than vendoring a
copy into this repo. It watches `~/.local/state/theme` and switches colorscheme
when `theme apply` runs. It also parses the tool's own `history.jsonl` for
rejections and drops those themes from the `<leader>fz` picker, so a theme
rejected anywhere never comes back as a suggestion here.

That coupling is deliberate but load-bearing. The theme tool owns both paths, so
a change to where it writes its state breaks Neovim's switching silently — the
editor simply stops following an apply.

## See Also

- [Nerd Fonts Explained](https://docs.ichrisbirch.com/fonts/nerd-fonts-explained/) — what Nerd Fonts are and why they matter
- [Font Weights and Variants](https://docs.ichrisbirch.com/fonts/font-weights-and-variants/) — understanding Bold/Italic/Light variants
- [Terminal Fonts Guide](https://docs.ichrisbirch.com/fonts/terminal-fonts-guide/) — why monospace matters for terminals
- [Font Comparison](https://docs.ichrisbirch.com/fonts/font-comparison/) — detailed comparison of font families
