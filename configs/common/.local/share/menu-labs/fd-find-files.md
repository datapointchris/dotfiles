---
tags: [fd, find, search, files]
cadence: 3w
---

# Find files fast with fd

> `fd` is the `find` you'll actually remember. This Lab drills the flags you
> reach for weekly — by name, extension, type, hidden/ignored, recency, and
> running a command on every match — on a throwaway tree.

## Setup

Copy this into your other pane to build a scratch tree and drop into it:

```bash
LAB=$(mktemp -d) && cd "$LAB"
mkdir -p src/api src/web docs .cache
touch src/api/server.go src/api/server_test.go src/web/app.tsx docs/readme.md
touch .cache/junk.log old.log
printf 'TODO: fix\n' > src/web/notes.txt
# make one file "old" so --changed-within has something to exclude
touch -d '40 days ago' old.log
```

## Steps

1. **Search by name fragment.** `fd server`
   - Expect: `src/api/server.go` and `src/api/server_test.go`.
   - Why: `fd <pattern>` is a smart-case regex match on the *filename*, recursive
     from the cwd. It skips `.gitignore`d paths and dotfiles by default — which is
     exactly why `.cache/junk.log` does not appear.

2. **Filter by extension.** `fd -e go`
   - Expect: just the two `.go` files.
   - Why: `-e` matches the extension exactly (no leading dot) and is repeatable:
     `fd -e go -e tsx`.
   - Alternative: `fd '\.go$'` works, but `-e` is shorter and says what it means.

3. **Include hidden + ignored.** `fd -H log`
   - Expect: now `.cache/junk.log` and `old.log` show up.
   - Why: `-H` stops honoring ignore files and dotfile-hiding — your "why isn't my
     file showing up?" escape hatch. Add `-I` for ignored-but-not-hidden.

4. **Filter by type.** `fd -t d` then `fd -t f -e tsx`
   - Expect: the directories; then only `src/web/app.tsx`.
   - Why: `-t d` / `-t f` filter by entry type and combine with any other flag.

5. **Filter by recency.** `fd --changed-within 7d`
   - Expect: everything except `old.log`.
   - Why: `--changed-within` / `--changed-before` beat `find -mtime` arithmetic
     for "what did I touch this week".

6. **Run a command on every match.** `fd -e go -x wc -l`
   - Expect: a line count per `.go` file.
   - Why: `-x` runs the command once per result, in parallel. `{}` is the path,
     `{/}` the basename, `{.}` the path without extension.
   - Alternative: `-X` passes *all* matches to one invocation: `fd -e go -X ls -l`.

## The whole thing in one breath

```bash
fd -e go -x wc -l                 # count lines in every Go file
fd -H -t f --changed-within 1d    # every file, even hidden, touched today
```
