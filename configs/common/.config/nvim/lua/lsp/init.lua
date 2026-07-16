-- ================================================================== --
-- LSP Configuration
-- ================================================================== --
-- This module handles all LSP-related setup including:
-- - Advertising blink.cmp client capabilities to every server
-- - Enabling language servers
-- - Completion settings (completeopt)
-- - Diagnostic configuration
-- Buffer-local on-attach behaviour lives in core/autocmds.lua.

-- Advertise blink.cmp's client capabilities (snippet support, resolve, etc.)
-- to every server. Setting them on the '*' config means each server receives
-- them in its initialize request; deep-merges with per-server capabilities
-- (e.g. gh_actions_ls). This is the correct wiring — the old approach merged
-- them into client.server_capabilities on attach, which was too late and the
-- wrong direction (server_capabilities describe what the server offers).
if pcall(require, 'blink.cmp') then
  vim.lsp.config('*', { capabilities = require('blink.cmp').get_lsp_capabilities() })
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

-- Buffer-local LSP behaviour on attach (K hover override, per-server capability
-- tweaks) lives in the single LspAttach autocmd in core/autocmds.lua.

-- Set completeopt for blink.cmp compatibility
vim.opt.completeopt = { 'menu', 'menuone', 'noinsert', 'noselect' }

-- Configure diagnostic display
vim.diagnostic.config({
  -- virtual_text = { current_line = true },
  virtual_text = true,
  float = { border = 'rounded' },
})
