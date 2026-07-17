---
tags: [neovim, registers, clipboard, keymaps, editing]
cadence: 1mo
---

# Keep your yank while you edit (register-safe moves)

> The classic Vim annoyance: you yank something, delete to make room, and the
> delete clobbers the yank. Your config has keymaps that fix this. This Lab
> drills them. Leader is Space.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
cat > demo.txt <<'EOF'
keep this line
some junk to overwrite
delete this whole line
reorder me
anchor line
EOF
nvim demo.txt
```

## Steps

1. **Delete without losing your yank.** `yy` on line 1 → move to line 3 →
   `<leader>dd` → go to the end of the file → `p`.
   - Expect: line 3 is gone, and what pastes is still line 1 — not line 3.
   - Why: `<leader>d` deletes into the black-hole register (`"_d`), so your yank
     survives. Plain `dd` would have overwritten it.

2. **Paste over a selection without clobbering.** `yiw` on "keep" → visually select
   "junk" (`viw`) → `<leader>P`.
   - Expect: "junk" becomes "keep", and you can `<leader>P` the same word again
     elsewhere.
   - Why: `<leader>P` in visual mode does `"_dP` — black-hole the selection, then
     paste — so the yanked word isn't replaced by what you overwrote. Plain `p`
     over a selection swaps your register for the deleted text.

3. **Single-char delete stays clean.** `x` on any character.
   - Expect: the char is removed, your yank register untouched.
   - Why: `x` is remapped to `"_x`, so quick deletes never disturb what you carry.

4. **Reach the system clipboard on purpose.** `<leader>y` on a selection, paste it
   in another app; `<leader>p` pastes *from* the system clipboard.
   - Expect: content crosses the app boundary.
   - Why: `<leader>y` / `<leader>p` target the `+` register explicitly, so plain
     `y` / `p` stay fast and local and the clipboard is opt-in.

5. **Move a line without cut-and-paste.** on "reorder me", `V` then `J` / `K`.
   - Expect: the selected line slides down / up, re-indenting as it goes.
   - Why: visual `J` / `K` are remapped to move the selection, not join lines — the
     ergonomic way to reorder without touching a register at all.
