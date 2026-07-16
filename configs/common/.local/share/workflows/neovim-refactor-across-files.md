---
tags: [neovim, telescope, grep, quickfix, cdo, cfdo, rename, replace, refactor, recipe, mass-edit]
---

# neovim refactor across files (grep to quickfix to mass edit)

```bash
# GOAL: change some text in EVERY file a search returned
# (rename a variable, swap a string, replace an import) start to finish.
# Reach for this when it is NOT a single LSP symbol — strings, comments,
# config, or text spanning multiple languages. For one real symbol,
# skip all of this and use the LSP shortcut at the bottom.

# 1. SEARCH — find every occurrence
<leader>fg           live grep the whole project (telescope)
                     type the text/pattern you want to change
<C-/>                (while in telescope) show EVERY keybinding for this
?                    picker — same, from normal mode. This is how you
                     remember the keys below without leaving the picker.

# 2. COLLECT — send the matches into the quickfix list
<C-q>                send ALL results to the quickfix list + open it
<Tab>                (optional) mark individual entries first...
<M-q>                ...then send ONLY the marked entries to quickfix
                     Rule: <C-q> = everything the grep found,
                           <M-q> = just the ones you Tab-marked.

# 3. REVIEW — look at what you captured before editing
<leader>xq           open the quickfix list in Trouble (nicest view)
<leader>fq           or fuzzy-search the quickfix list (telescope)
]q  /  [q            jump to next / previous entry in the file itself

# 4. EDIT EVERY MATCH — run one command over the whole list
:cfdo %s/OLD/NEW/ge | update    once PER FILE (use for renames)
:cdo   s/OLD/NEW/g  | update    once PER MATCHING LINE
                     \<OLD\>    add word boundaries to rename whole words only
                     e flag     (%s/..//ge) = do not abort if a file lacks it
                     | update   writes each changed buffer (only if modified)

# WHY | update MATTERS (the gotcha that bites)
# cdo/cfdo switch buffers as they go. Without saving, the second file
# errors with E37 (no write since last change). "| update" saves after
# each step so the walk completes and your changes actually hit disk.

# THE WHOLE THING IN TWO LINES (the common case)
<leader>fg  ->  type pattern  ->  <C-q>
:cfdo %s/\<oldName\>/newName/ge | update

# SHORTCUT — if it is ONE real symbol the LSP understands, do this instead
<leader>cr           inc-rename: live-preview rename of the word under the
                     cursor across the whole project, semantically correct.
                     No grep, no quickfix — LSP renames only true references.
```
