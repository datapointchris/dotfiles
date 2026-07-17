---
tags: [neovim, mini, surround, textobjects, editing]
cadence: 1mo
---

# Edit structurally with surround and text objects

> The leap from "delete some characters" to "change *this argument*" is text
> objects. This Lab drills mini.ai text objects, mini.surround, and treesitter
> function objects on a staged file. Leader is Space; `u` undoes between steps.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
cat > demo.py <<'EOF'
def greet(name, greeting):
    message = 'hello ' + name
    return greeting(message)
EOF
nvim demo.py
```

## Steps

1. **Change inside quotes.** cursor on the `'hello '` string → `ci'` → type `hi` →
   Esc.
   - Expect: `'hello '` becomes `'hi'`.
   - Why: `i'` is the inside-quotes text object (mini.ai); `c` changes it. `ci(`,
     `ci{`, `ci[` do brackets; `cit` an HTML/XML tag.

2. **Add a surround.** cursor on `name` (line 2) → `saiw)`
   - Expect: `name` becomes `(name)`.
   - Why: mini.surround `sa` = surround-add; `iw` picks the target (inner word),
     `)` the pair. `saiw"` would quote it instead.

3. **Replace a surround.** cursor inside the new `(name)` → `sr)'`
   - Expect: `(name)` becomes `'name'`.
   - Why: `sr` = surround-replace — old pair `)`, new pair `'`. One motion instead
     of delete-both-ends-and-retype.

4. **Delete a surround.** cursor inside a quoted string → `sd'`
   - Expect: the quotes vanish, text stays.
   - Why: `sd` = surround-delete; `'` names the pair to strip.

5. **Operate on a whole function.** cursor anywhere in the def → `vaf`
   - Expect: the entire function is selected.
   - Why: `af` = "a function" (treesitter text object); pair it with any operator —
     `daf` deletes it, `yaf` yanks it. `]f` / `[f` jump between functions.

## The whole thing in one breath

```text
ci(     change inside parentheses
saiw"   quote the word under the cursor
sr'`    swap surrounding quotes for backticks
daf     delete the whole function (treesitter)
```
