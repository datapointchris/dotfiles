-- Use LSP hover instead of pydoc for K
-- Empty keywordprg lets Neovim 0.11+ default K mapping use vim.lsp.buf.hover()
vim.opt_local.keywordprg = ''
