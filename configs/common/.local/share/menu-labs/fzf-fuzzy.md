---
tags: [fzf, fuzzy, search, interactive, keybindings]
cadence: 1mo
---

# Fuzzy-find anything with fzf

> `fzf` is the interactive filter behind half your shortcuts. This Lab drills the
> shell keybindings and the pipe pattern so reaching for it is automatic.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
mkdir -p src/api src/web docs
touch src/api/server.go src/api/db.go src/web/app.tsx docs/readme.md
```

## Steps

These are interactive — do them in the pane you're working in.

1. **Filter a pipe.** `fd . | fzf`
   - Expect: a full-screen fuzzy filter over the file list; type to narrow, Enter
     prints the pick, Esc cancels.
   - Why: `fzf` reads stdin, filters interactively, writes the selection to
     stdout — so it composes with anything.

2. **File-insert widget.** Type `nvim` (trailing space), then press `Ctrl-T`.
   - Expect: an fzf picker of files; your choice is inserted onto the command
     line after `nvim`.
   - Why: `Ctrl-T` pastes a fuzzy-picked path into the current command — no typing
     or tab-cycling.

3. **History search.** Press `Ctrl-R`.
   - Expect: fuzzy search over shell history; Enter runs (or edits) the pick.
   - Why: `Ctrl-R` replaces reverse-i-search with fuzzy matching — find last
     week's command by any word in it.

4. **cd widget.** Press `Alt-C`.
   - Expect: a fuzzy directory picker; the pick becomes your cwd.
   - Why: `Alt-C` fuzzy-cds into a subdirectory. (`z` covers *frequent* dirs;
     `Alt-C` covers *any* subdir of here.)

5. **Preview while you pick.** `fd -t f | fzf --preview 'bat --color=always {}'`
   - Expect: the highlighted file's contents in a side pane as you move.
   - Why: `--preview` runs a command per highlighted line (`{}` = the line) — the
     same mechanic `menu` and `menu labs pick` use.

## The whole thing in one breath

```text
Ctrl-R                        find a past command by any word
Ctrl-T                        insert a fuzzy-picked file path
nvim $(fzf --preview 'bat --color=always {}')   pick a file, previewed, and open it
```
