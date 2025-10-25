-- ================================================================== --
-- Environment Validation
-- ================================================================== --
-- Validate required environment variables for proper configuration
local required_env_vars = {
  'PLATFORM',
  'NVIM_AI_ENABLED',
}

local missing_vars = {}
for _, var in ipairs(required_env_vars) do
  if not vim.env[var] then
    table.insert(missing_vars, var)
  end
end

if #missing_vars > 0 then
  vim.notify(
    'Missing required environment variables: ' .. table.concat(missing_vars, ', ') .. '\nPlease check your ~/.env file',
    vim.log.levels.ERROR,
    { title = 'Environment Error' }
  )
end

-- Always load core configuration
require('core.options')
require('core.lazy') -- Load lazy.nvim in both VSCode and Neovim
require('core.keymaps')

-- Only load autocmds in regular Neovim
if not vim.g.vscode then
  require('core.autocmds')
end

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

vim.cmd('set completeopt+=noselect')

vim.diagnostic.config({
  -- virtual_text = { current_line = true },
  virtual_text = true,
  float = { border = 'rounded' },
})
