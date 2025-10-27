-- ================================================================== --
-- LSP Configuration
-- ================================================================== --
-- This module handles all LSP-related setup including:
-- - Server capabilities for nvim-cmp integration
-- - Enabling language servers
-- - LspAttach autocmd for capability merging
-- - Completion settings (completeopt)
-- - Diagnostic configuration

-- Set up LSP client capabilities for nvim-cmp before enabling servers
local capabilities = nil
if pcall(require, 'cmp_nvim_lsp') then
  capabilities = require('cmp_nvim_lsp').default_capabilities()
end

vim.lsp.enable({
  'bashls',
  'basedpyright',
  'cssls',
  'docker_language_server',
  'eslint',
  'gh_actions_ls',
  'gopls',
  'html',
  'jsonls',
  'lua_ls',
  'marksman',
  'ruff',
  'rust_analyzer',
  'sqls',
  'taplo',
  'terraformls',
  'tflint',
  'ts_ls',
  'yamlls',
})

-- Set up LSP capabilities for nvim-cmp integration
vim.api.nvim_create_autocmd('LspAttach', {
  callback = function(ev)
    local client = vim.lsp.get_client_by_id(ev.data.client_id)
    if client and capabilities then
      -- Merge cmp capabilities with client capabilities
      client.server_capabilities = vim.tbl_deep_extend('force', client.server_capabilities or {}, capabilities)
    end
  end,
})

-- Disable native LSP completion since we're using nvim-cmp
-- vim.api.nvim_create_autocmd('LspAttach', {
--   callback = function(ev)
--     local client = vim.lsp.get_client_by_id(ev.data.client_id)
--     if client:supports_method('textDocument/completion') then
--       vim.lsp.completion.enable(true, client.id, ev.buf, { autotrigger = true })
--     end
--   end,
-- })

-- Set completeopt for nvim-cmp compatibility
vim.opt.completeopt = { 'menu', 'menuone', 'noinsert', 'noselect' }

-- Configure diagnostic display
vim.diagnostic.config({
  -- virtual_text = { current_line = true },
  virtual_text = true,
  float = { border = 'rounded' },
})
