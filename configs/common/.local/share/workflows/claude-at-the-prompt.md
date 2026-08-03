---
tags: [zsh, claude, ai, keybindings, autosuggestions, atuin, zle, reference]
---

# ask Claude from the zsh prompt, and what else offers you commands

```bash
# THREE DIFFERENT THINGS OFFER YOU A COMMAND. They are not competing — each one
# knows something the others do not, and they are reached by different keys.
#
#   ghost text      what YOU have run before        free, appears as you type
#   Ctrl-R          what you have run before        a deliberate search, with cwd + exit code
#   Ctrl-X Ctrl-A   what you have NEVER run         costs a Claude round trip, ~5s

# ── 1. GHOST TEXT (zsh-autosuggestions) ─────────────────────────────────────
# Grey text ahead of the cursor, drawn from history; falls back to completion
# when history has nothing. Purely passive — it never runs anything.
End        # accept the whole suggestion
Ctrl-E     # same thing (zsh-vi-mode binds ^E to end-of-line)
# Nothing partially accepts: forward-word is unbound here, so Alt-f does not
# take one word. Accept it all and delete back, or keep typing to narrow it.

# ── 2. Ctrl-R (atuin) ───────────────────────────────────────────────────────
# SQLite-backed history search. Richer than the ghost text because it shows when
# you ran it, in which directory, and whether it exited 0.

# ── 3. Ctrl-X Ctrl-A — ASK CLAUDE ───────────────────────────────────────────
# Type the English on the prompt line, press it, and the line is REPLACED by the
# command that does it. Nothing executes: read it, edit it, then Enter.
#
#   show the 5 largest files in this directory   →   Ctrl-X Ctrl-A
#   eza -lbF --only-files --sort=size --reverse | head -n 5
#
# The prompt blocks for a few seconds and shows "⋯ asking claude" while it waits.
# It is told the OS and that fd/rg/eza/jq/yq are installed, so what comes back is
# GNU-vs-BSD correct and does not reach for find/grep.

# ── 4. Ctrl-X Ctrl-E — EXPLAIN THIS LINE ────────────────────────────────────
# The inverse. Keeps the line exactly as it is and prints a few lines underneath
# saying what it does, flag by flag, leading with a warning if it is destructive.
# Use it on anything Ctrl-X Ctrl-A hands you that you do not recognise.

# ── SAME THING, WITHOUT A PROMPT LINE ───────────────────────────────────────
doshell find every file over 100MB under my home directory
# Loads the answer at your NEXT prompt via `print -z`, and copies it to the
# clipboard. Use this when you are starting from nothing; use Ctrl-X Ctrl-A when
# you are already halfway through typing and stuck.

# ── WHY `?` DOES NOTHING SPECIAL ────────────────────────────────────────────
# atuin ships its own natural-language mode bound to `?` on an empty line. It is
# switched off in ~/.config/atuin/config.toml ([ai] enabled = false) because
# using it means an Atuin Hub account or self-hosting atuin-ai-server, and the
# widgets above already cover it through the Claude subscription. Left on, it
# stole `?` as the first character of a line.
```

## Where this lives

The widgets are defined in the SHELL CONFIG section of `.zshrc` and bound inside
`zvm_after_init`, because zsh-vi-mode wipes the keymap once the rc file finishes.
The Claude calls themselves are `doshell_suggest_command` and
`doshell_explain_command` in `shell/common/functions.sh`, shared with `doshell`.

Ctrl-X chords rather than Alt: `^[` is vi-cmd-mode, so every Meta binding makes
Escape wait out KEYTIMEOUT before it switches modes. `^X^A` and `^X^E` were the
free ones — the rest of the `^X` space is zsh's completion-debug bindings.
