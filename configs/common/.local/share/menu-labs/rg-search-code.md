---
tags: [rg, ripgrep, search, grep, code]
cadence: 3w
---

# Search code fast with ripgrep

> `rg` is your first move for "where is this used?". This Lab drills the flags
> that turn a flat search into a precise one — file types, whole-word matches,
> context, listing files, and previewing a replace before you touch anything.

## Setup

Copy this into your other pane to stage a small tree and drop into it:

```bash
LAB=$(mktemp -d) && cd "$LAB"
mkdir -p src tests
cat > src/app.py <<'EOF'
def connect(timeout=30):
    # TODO: make timeout configurable
    return open_conn(timeout)

def retry(timeout=5):
    return connect(timeout)
EOF
cat > src/util.js <<'EOF'
export const timeout = 30; // TODO drop this
export function wait(timeout) { return timeout; }
EOF
cat > tests/test_app.py <<'EOF'
def test_connect():
    assert connect(timeout=1)
EOF
```

## Steps

1. **Plain search.** `rg timeout`
   - Expect: matches across all three files, grouped by file with line numbers.
   - Why: `rg` is recursive, smart-case, and `.gitignore`-aware by default, and it
     colorizes the matched span so hits are easy to scan.

2. **Restrict by language.** `rg timeout -t py`
   - Expect: only the two Python files.
   - Why: `-t py` filters by file type (`rg --type-list` shows them); `-T py`
     excludes it. Cleaner than globbing extensions.

3. **Whole word only.** `rg -w timeout`
   - Expect: same hits here, but this would skip `timeouts` or `set_timeout`.
   - Why: `-w` bounds the match to word edges — the fix for "my search matched a
     substring inside a longer identifier".

4. **Add context.** `rg -C2 TODO`
   - Expect: each TODO with two lines above and below.
   - Why: `-C n` (or `-A` / `-B` for after / before) shows why a line matters
     without opening the file.

5. **List just the files.** `rg -l connect`
   - Expect: `src/app.py` and `tests/test_app.py`.
   - Why: `-l` prints file paths only — made to pipe into an editor:
     `nvim $(rg -l connect)`.

6. **Preview a replace.** `rg timeout -r deadline`
   - Expect: the matches printed with `timeout` → `deadline`, on screen only.
   - Why: `-r` shows what a replacement *would* look like without writing a byte —
     a safe dry run. To actually apply it, reach for `sd timeout deadline` or
     `sed -i` on the files `rg -l` gave you.

## The whole thing in one breath

```bash
rg -t py -w -C1 timeout      # whole-word 'timeout' in Python, with context
nvim $(rg -l TODO)           # open every file with a TODO
```
