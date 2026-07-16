---
tags: [neovim, telescope, grep, pickers, keybindings]
---

# telescope pickers and keys

```bash
# THE ONE TO REMEMBER — discover keys without leaving the picker
<C-/>             (insert mode) show ALL keybindings for the current picker
?                 (normal mode) same — this is the built-in cheat sheet

# Open pickers (your keymaps)
<leader>ff        find files
<leader>fg        live grep (search file contents across the project)
<leader>fb        buffers
<leader>fq        quickfix list        <leader>fl   location list
<leader>fs        LSP document symbols
<leader>fk        keymaps (search every mapping by description)
<leader>fh        help tags            <leader>fc   commands
<leader>fr        registers            <leader>ft   treesitter symbols
<leader>fn        neovim config files  <leader>fz   colorschemes

# Move / preview inside a picker
<C-n> / <C-p>     next / previous result (also arrow keys)
<C-u> / <C-d>     scroll the preview window up / down
<CR>              open selection        <C-x> / <C-v>   open in split / vsplit
<C-t>             open in a new tab
<Esc> / <C-c>     close the picker

# Multi-select + quickfix (feeds the refactor-across-files recipe)
<Tab>             mark this entry (and move down)   <S-Tab>  mark + move up
<C-q>             send ALL results to the quickfix list + open it
<M-q>             send only the MARKED entries to the quickfix list

# Handy
<leader>fg then type, then <C-q>   grep -> quickfix in two steps
# For editing every quickfix entry afterward: workflows show neovim-refactor-across-files
```
