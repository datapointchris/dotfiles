# git file operations — mv, rm, and staging for clean history

Use git-native commands so renames/deletes show up as renames/deletes in the log,
not as unrelated add+delete pairs.

## Move / Rename

```bash
git mv old/path.go new/path.go           # rename a file
git mv internal/backend backend          # rename a directory (if dest doesn't exist)
git mv src/foo.go src/bar.go             # rename in place
```

Git tracks renames by content similarity (≥50% match = rename, not delete+add).
Using `git mv` makes the rename explicit in the index regardless of similarity.

```bash
git diff --stat                          # shows: {old => new}/file.go (95%)
git log --follow new/path.go             # trace history through the rename
git log --diff-filter=R --summary        # list all rename commits
```

## Delete

```bash
git rm path/to/file.go                   # remove tracked file + stage the deletion
git rm -r internal/undo/                 # remove tracked directory recursively
git rm --cached file.go                  # untrack without deleting from disk (gitignore candidates)
```

## Partial Staging

```bash
git add -p file.go                       # interactively stage hunks (y/n/s/e)
git add -p                               # walk all unstaged changes hunk by hunk
```

## Common Housekeeping Patterns

```bash
# Rename a package directory and update imports (structural refactor)
git mv internal/model model
# ... edit files (sed/find-replace imports) ...
git add model/                           # stage the import changes
git commit                               # git sees renames + edits in one commit

# Remove a file that was accidentally committed
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: untrack .env, add to gitignore"

# Stage only specific files after a broad edit
git add backend/local.go sync/engine.go  # explicit paths, never git add .
git diff --staged                        # verify before committing
```

## Why It Matters

- `mv` + `git add -A` records a delete + add — history is lost at the old path
- `git mv` stages the rename atomically — `git log --follow` works across the rename
- `git rm` vs `rm` + `git add`: same principle — keeps the intent explicit in the diff
