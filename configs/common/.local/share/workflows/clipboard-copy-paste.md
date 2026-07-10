---
tags: [clipboard, copy, paste, tmux, neovim, zsh, vi-mode, copy-mode]
---

# clipboard — copy & paste across neovim, zsh, tmux, macOS/WSL

**Explicit model.** Plain `y`/`d`/`p` in each program stay *inside that program*.
To move text between programs you deliberately send it through the system
clipboard with a dedicated key. Deletes never touch the clipboard, so the OS
clipboard history stays clean.

## The four buckets

There isn't one clipboard — there are three private ones and one shared:

- **System clipboard** — the only shared bucket; what `cmd+c`/`cmd+v` and your
  clipboard-history manager use. macOS: `pbcopy`/`pbpaste`. WSL: the Windows
  clipboard via `win32yank.exe`.
- **Neovim registers** — private to each nvim process. `"` = default; `+` is a
  window into the system clipboard.
- **Zsh cut buffer** — private to each shell's line editor; `p`/`P` paste it.
- **Tmux paste buffers** — private to the tmux server; `prefix ]` pastes them.

Nothing crosses into the shared bucket unless a key explicitly puts it there.

## Keybinds

```text
NEOVIM (leader = Space)
INTERNAL — this nvim only            SYSTEM CLIPBOARD — crosses apps
y   yank   → " register              <leader>y   yank selection → clipboard
d   delete → " register              <leader>Y   yank line      → clipboard
p   paste    " register              <leader>p   paste          ← clipboard
c   change → " register              <leader>d   delete → black hole (no reg)

ZSH — vi mode on the command line (press Esc for normal mode first)
INTERNAL — this shell only           SYSTEM CLIPBOARD
y / d / x  → cut buffer              gp   paste after cursor  ← clipboard
p / P      paste cut buffer          gP   paste before cursor ← clipboard
(to copy the command line OUT to the clipboard, use tmux copy-mode below,
 or pipe:  print -r -- "$cmd" | pbcopy)

TMUX
COPY → system clipboard              PASTE / MOVE
prefix [   enter copy mode           prefix ]   paste tmux buffer into pane
v          begin selection           prefix P   paste tmux buffer into pane
Ctrl-v     rectangle (block) select  Ctrl+h/j/k/l   move between panes
y          yank selection → clip     prefix y   copy current command line → clip
Enter      yank + exit copy mode     prefix Y   copy pane's cwd → clip

GHOSTTY / any GUI app (browser, Claude Code input)
cmd+c   copy → system clipboard      cmd+v   paste ← system clipboard
```

## Two golden rules

1. **Plain `y`/`p` is private.** To move text *between* programs it must go
   through the system clipboard: `<leader>y`/`<leader>p` in nvim, `gp` in zsh,
   copy-mode `y` / `prefix ]` in tmux, `cmd+c`/`cmd+v` in a GUI.
2. **Paste with the target's own paste command, never `cmd+v` into a normal-mode
   editor or shell.** `cmd+v` types the text as keystrokes — autoindent then
   cascades the indentation in nvim, and the shell runs each line early. `<leader>p`
   / `gp` insert the text verbatim into the buffer, so multi-line commands land
   intact and nothing runs until you press Enter once.

## Examples

**1 — nvim → terminal (multi-line command, keep formatting).**
In nvim, visually select the command (`V` + motions, or `vip`) → `<leader>y`.
Move to the terminal pane (`Ctrl+h`). In zsh normal mode → `gp`. The whole
command drops onto the command line intact; press Enter to run. (Both ends are
register operations, so the spacing is preserved and nothing runs mid-paste.)

**2 — tmux terminal output → Claude Code.**
In the terminal pane: `prefix [` → copy mode, `v` to start, select the output,
`y` (copies to clipboard, exits copy mode). Move to the Claude pane (`Ctrl+l`)
→ `cmd+v` into Claude's input.

**3 — nvim ↔ nvim (two instances, side by side).**
The two nvim processes do **not** share registers, so plain `y`/`p` won't work
across them — you must use the clipboard. Source nvim: select → `<leader>y`.
Move panes (`Ctrl+l`). Target nvim: `<leader>p` (not `p`).

**4 — browser → Claude Code.**
Browser `cmd+c`. If Claude is in Ghostty: `cmd+v` into its input. If Claude is
in a tmux pane: still just `cmd+v` — Ghostty's paste passes straight through
tmux into Claude; the tmux layer doesn't intercept a terminal-level paste.

**5 — Claude Code (in tmux) → nvim or browser.**
Claude's output is terminal text: `prefix [` → select → `y` (→ clipboard). For
nvim, move to its pane (`Ctrl+h`) → `<leader>p`. For the browser → `cmd+v`.

**6 — Claude Code → run a multi-line command in another tmux pane.**
This is the one that always broke: pasting the block used to run line-by-line
and the indentation mangled the shell. Fix — get it to the clipboard, then paste
with `gp` (a register paste, not keystrokes):

1. Copy the command from Claude: `prefix [`, select just the command lines
   (avoid any box border), `y`.
2. Move to the target shell pane (`Ctrl+l`).
3. zsh normal mode → `gp`. The multi-line command lands in the command line as
   one editable block — leading whitespace is ignored by zsh and nothing
   executes. Review it, then press Enter once to run.
