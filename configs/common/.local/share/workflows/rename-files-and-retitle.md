---
tags: [fd, ripgrep, yazi, neovim, rename, sed, files, recipe, mass-edit]
---

# rename files and retitle (pattern-select → bulk-rename → sync in-file title)

```bash
# GOAL: pick a set of files by pattern, bulk-rename them, then update a title
# INSIDE each file (e.g. a markdown "# Heading") to match its NEW filename.
# Two paths below: interactive (yazi + nvim) and headless (fd + sed).

# 1. SELECT — which files?
fd 'pat' -t f          # by NAME (regex on the path; -t f = files only)
fd -e md 'pat'         # ...restricted to an extension (-e, repeatable)
rg -l 'content'        # by CONTENT — files that CONTAIN the pattern (-l = names)
                       # `fd`/`rg` both respect .gitignore; add -H -I to include
                       # hidden/ignored.

# 2a. BULK RENAME — interactive (yazi)
y                      # open yazi (aliased) in the dir
<Space>                # toggle-select each target file (or `v` for a range)
r                      # with MULTIPLE selected, `r` opens ALL names in $EDITOR,
                       #   one per line. Edit the lines, :wq — yazi applies the
                       #   diff on save. (single file: `r` renames inline.)

# 2b. BULK RENAME — headless (shell), no editor
fd 'oldpat' -t f -x mv {} {.}-renamed.md   # {.} = path minus extension; craft
                                           #   the new name from {} / {.} / {/}.

# 3. OPEN the renamed set in one nvim (as the arglist)
nvim $(fd 'newpat')    # every match becomes an :args entry

# 4. RETITLE — sync the in-file H1 to each new filename (interactive)
:argdo %s/\v^#\s+.*/\='# ' . expand('%:t:r')/ | update
                       # expand('%:t:r') = filename, no dir, no extension.
                       # \v = very-magic regex. | update saves each buffer as
                       # :argdo walks (the E37 save-gotcha, same as the refactor card).

# 4b. RETITLE — headless (GNU sed, first H1 only)
fd -e md 'newpat' -x sh -c 'f="$1"; \
  sed -i "0,/^# /s|^# .*|# $(basename "$f" .md)|" "$f"' _ {}
                       # 0,/^# / is a GNU-sed range = "up to the FIRST # line",
                       # so only the title heading is rewritten.
```

## The whole thing in two lines (markdown, interactive)

```bash
# yazi: <Space> the files → r → fix names in $EDITOR → :wq
nvim $(fd 'newpat')  then  :argdo %s/\v^#\s+.*/\='# '.expand('%:t:r')/ | update
```

## Gotchas

```bash
# - nvim's %s retitles EVERY `# ` line in a file, not just the first. If a doc
#   has multiple H1s, use the sed `0,/^# /` range (4b) which stops at the first.
# - | update is mandatory in :argdo — without it the 2nd file errors E37
#   (no write since last change) and the walk halts.
# - yazi bulk-rename only applies when you SAVE the editor buffer. Quit without
#   writing and nothing renames.
# - `sd`/`rename` are NOT installed here — use GNU `sed -i` (env is GNU-tools).
```

Complements `neovim-refactor-across-files` (that one edits CONTENT across grep
matches; this one RENAMES files and syncs their titles).
