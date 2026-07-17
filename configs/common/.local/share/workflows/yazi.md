---
tags: [yazi, file-manager, tui, navigation, keybindings, search]
---

# yazi — terminal file manager (selection, pattern matching, shell commands)

Self-discovery: press `~` (or `F1`) for searchable help — inside it, `f` filters the key list. That is the fastest way to find "how do I do X" without leaving yazi.

## Navigate

| Key | Action |
| --- | --- |
| `h` / `l` | Parent dir / enter dir |
| `j` / `k` | Down / up |
| `gg` / `G` | Top / bottom |
| `H` / `L` | Back / forward in history (not up/down a dir) |
| `<C-u>`/`<C-d>` | Half page up / down |
| `gh` `gc` `gd` | cd home / `~/.config` / `~/Downloads` |
| `g<Space>` | cd interactively (type a path) |
| `z` / `Z` | Jump via fzf / zoxide |
| `Tab` | Spot — full metadata view of hovered file |

## Select multiple files

| Key | Action |
| --- | --- |
| `<Space>` | Toggle this file's selection, advance to next |
| `v` / `V` | Visual mode: select range / deselect range |
| `<C-a>` | Select all in dir |
| `<C-r>` | Invert selection |
| `<Esc>` | Clear selection / exit visual mode |

Selection persists across directories — select here, `l` into another dir, keep adding, then act on all at once.

## Pattern matching — find vs filter vs search (the three that get confused)

| Key | Command | Scope | What it does |
| --- | --- | --- | --- |
| `/` `?` | `find` | current dir only | Jump cursor to next/prev name match (like vim `/`); `n`/`N` to repeat |
| `f` | `filter` | current dir only | Hide entries that don't match the typed pattern |
| `s` | `search --via=fd` | **recursive** | Populate the list with files matching a name pattern in all subdirs |
| `S` | `search --via=rg` | **recursive** | Populate the list with files whose *content* matches (ripgrep) |
| `<C-s>` | | | Cancel an active recursive search, return to normal listing |

Rule of thumb: `find`/`filter` stay in the folder you're looking at; `s`/`S` dive into the whole tree. After a recursive `s`/`S`, `<Esc>` or `<C-s>` clears it.

## File operations

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| `y` / `x` | Yank (copy) / cut selection | `p` / `P` | Paste / paste-overwrite |
| `a` | Create file (trailing `/` = dir) | `r` | Rename (cursor before extension) |
| `d` / `D` | Trash / delete permanently | `o` / `O` | Open / open-with (interactive) |

## Run shell commands on the selection

`;` runs a command without waiting; `:` runs it blocking (stays until you press enter). You type the command and reference the selected files with placeholders:

```sh
;  mv "$@" ~/archive/          # $@ = all selected files (or hovered if none selected)
:  unzip "$0"                  # $0 = the hovered file only
:  wc -l "$@"                  # blocking, so you see the output
;  convert "$0" "${0%.png}.jpg"
```

`$@` = every selected file, `$0` = hovered file, `$PWD` = current dir. Use `:` when you want to read the output; `;` for fire-and-forget.

## Sort, display, tabs

| Prefix | Keys | Action |
| --- | --- | --- |
| `,` (sort) | `,m ,b ,e ,a ,n ,s ,r` | mtime / btime / ext / alpha / natural / size / random (capital = reverse) |
| `m` (linemode) | `ms mp mb mm mo mn` | show size / perms / btime / mtime / owner / none beside each file |
| tabs | `t` `1`-`9` `[` `]` `{` `}` | new tab / switch / prev-next / swap |
| `.` | | Toggle hidden files · `w` = task manager |

## Installed plugins (why they're there)

| Plugin | Trigger | What it gives you |
| --- | --- | --- |
| **git.yazi** | automatic | Git status symbols beside files in the listing (modified/added/ignored) — fetched live per directory |
| **what-size** | `. s` (dot then s) | Total size of the current selection, or of cwd if nothing selected |
| **nbpreview** | automatic on `*.ipynb` | Renders Jupyter notebooks in the preview pane instead of raw JSON |

Plugins are managed with `ya pkg` (`ya pkg list` / `ya pkg upgrade`); manifest is `~/.config/yazi/package.toml`.
