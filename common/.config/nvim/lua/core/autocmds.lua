vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('highlight-yank', { clear = true }),
  callback = function()
    vim.highlight.on_yank()
  end,
})

vim.api.nvim_create_autocmd('LspAttach', {
  desc = 'LSP: Disable hover capability from Ruff in favor of Pyright',
  group = vim.api.nvim_create_augroup('lsp_attach_disable_ruff_hover', { clear = true }),
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if client == nil then
      return
    end
    if client.name == 'ruff' then
      -- Disable hover in favor of Pyright
      client.server_capabilities.hoverProvider = false
    end
  end,
})

vim.api.nvim_create_autocmd('BufWritePre', {
  desc = 'Run linter and formatter on save',
  group = vim.api.nvim_create_augroup('FormatAndFixAllOnSave', { clear = true }),
  pattern = '*',
  callback = function()
    vim.lsp.buf.code_action({
      context = { only = { 'source.fixAll' }, diagnostics = {} },
      apply = true,
    })
    -- Use the same formatter logic as manual formatting
    require('utils.formatter').format_buffer({ async = false, show_notifications = false, timeout_ms = 1000 })
  end,
})

-- Set word wrapping for markdown and text files
vim.api.nvim_create_autocmd('BufWinEnter', {
  pattern = { '*.md' },
  callback = function()
    vim.opt.wrap = true
    vim.opt.linebreak = true
  end,
})

vim.api.nvim_create_autocmd('BufWinLeave', {
  pattern = { '*.md' },
  callback = function()
    vim.opt.wrap = false
    vim.opt.linebreak = false
  end,
})
