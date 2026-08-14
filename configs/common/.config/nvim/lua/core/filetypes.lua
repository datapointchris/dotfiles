-- Filetype detection for shebangs Neovim cannot resolve on its own.
--
-- A PEP 723 script starts `#!/usr/bin/env -S uv run --script`, so the interpreter
-- Neovim finds is `uv`. There is no filetype by that name, and the file falls
-- through to `conf` — no highlighting, no LSP, no formatter. Every uv script in
-- dotfiles hits this: `prs`, `pr-list-python` and `tmux-rearrange` are all Python
-- with no extension to fall back on.
--
-- Registered as a `.*` pattern at the lowest possible priority rather than as an
-- extension, because these files have no extension and the rule must never win
-- against a real one.
--
-- `vim.filetype.getlines` and `vim.filetype.matchregex` appear in the `:h
-- vim.filetype.add` example and are not public API in 0.12 — both are nil. The
-- buffer is read directly instead.

vim.filetype.add({
  pattern = {
    ['.*'] = {
      function(_, bufnr)
        local shebang = vim.api.nvim_buf_get_lines(bufnr, 0, 1, false)[1] or ''
        if shebang:match('^#!.*uv run') then return 'python' end
      end,
      { priority = -math.huge },
    },
  },
})
