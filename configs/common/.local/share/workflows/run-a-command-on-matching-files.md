---
tags: [fd, find, exec, batch, files, bulk, recipe]
---

# run a command on every matching file (fd -x / -X: find and act in one pass)

```bash
# GOAL: find a set of files and DO something to each — format, convert, chmod,
# delete stale ones — without a hand-written for-loop. fd finds AND executes.
# The whole skill is choosing -x vs -X and using the path placeholders.

# --- -x : run the command ONCE PER FILE (in parallel) ---
fd -e py -x ruff format              # format each .py file; runs concurrently
fd -e jpg -x convert {} {.}.webp     # per file: {} = full path, {.} = path w/o ext
fd -t f -x chmod 644                 # {} is implicit as the last arg if omitted

# --- -X : run the command ONCE with ALL results as arguments ---
fd -e py -X wc -l                    # one `wc -l` over the whole list → a total
fd -e md -X nvim                     # open every match in ONE nvim (as arglist)
#   Rule: -x = "do this TO each file" (N commands). -X = "give the whole list to
#   one command" (1 command). wc/ls/tar/nvim want -X; format/convert want -x.

# --- placeholders (with -x) ---
#   {}    full path            configs/app/main.py
#   {.}   path minus extension configs/app/main
#   {/}   basename             main.py
#   {//}  parent dir           configs/app
#   {/.}  basename minus ext   main

# --- narrow BEFORE executing ---
fd -e log --changed-within 2d -x gzip    # only files modified in the last 2 days
fd -e tmp --changed-before 1week -X rm   # stale temp files older than a week
fd -t x -x ...                           # -t x = executables only (also -t e = empty)
```

## The safe pattern (always preview a destructive exec)

```bash
fd -e tmp --changed-before 1week         # 1. SEE the list first (no -x/-X)
fd -e tmp --changed-before 1week -X rm   # 2. only then attach the destructive cmd
```

## Gotchas

```bash
# - fd respects .gitignore and skips hidden by default. Acting on ignored/hidden
#   files (dotfiles, build output)? add -H (hidden) and/or -I (ignore .gitignore).
# - -x runs in PARALLEL with no order guarantee. If order matters, add --threads=1.
# - Everything after -x/-X is the command, not fd flags — put fd's own flags
#   (-e, -t, --changed-within) BEFORE -x.
# - For rename + in-file retitle specifically, see rename-files-and-retitle;
#   this card is the general "find and run" case.
```
