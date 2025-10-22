-- Native LSP Configuration Manager
-- This module provides a centralized way to configure and enable native LSP servers

local M = {}

-- List of available language server configurations
local servers = {
  'bashls',
  'basedpyright',
  'cssls',
  'docker_compose_language_service',
  'dockerls',
  'eslint',
  'gopls',
  'html',
  'jsonls',
  'lua_ls',
  'marksman',
  'ruff',
  'rust_analyzer',
  'sqlls',
  'taplo',
  'terraformls',
  'tflint',
  'ts_ls',
  'vimls',
  'yamlls',
}

-- Default capabilities for all LSP servers
local function get_default_capabilities()
  local capabilities = vim.lsp.protocol.make_client_capabilities()

  -- Enable snippets
  capabilities.textDocument.completion.completionItem.snippetSupport = true
  capabilities.textDocument.completion.completionItem.resolveSupport = {
    properties = { 'documentation', 'detail', 'additionalTextEdits' },
  }

  -- Enable folding
  capabilities.textDocument.foldingRange = {
    dynamicRegistration = false,
    lineFoldingOnly = true,
  }

  return capabilities
end

-- Common on_attach function for all servers
local function on_attach(client, bufnr)
  -- Enable completion triggered by <c-x><c-o>
  vim.bo[bufnr].omnifunc = 'v:lua.vim.lsp.omnifunc'

  -- Enable native completion
  vim.lsp.completion.enable(true, client.id, bufnr, { autotrigger = true })

  -- Highlight references under cursor
  if client.supports_method('textDocument/documentHighlight') then
    local group = vim.api.nvim_create_augroup('lsp_document_highlight', { clear = false })
    vim.api.nvim_create_autocmd({ 'CursorHold', 'CursorHoldI' }, {
      buffer = bufnr,
      group = group,
      callback = vim.lsp.buf.document_highlight,
    })
    vim.api.nvim_create_autocmd('CursorMoved', {
      buffer = bufnr,
      group = group,
      callback = vim.lsp.buf.clear_references,
    })
  end

  -- Format on save for supported servers
  local format_on_save_servers = {
    'basedpyright',
    'gopls',
    'rust_analyzer',
    'lua_ls',
    'ts_ls',
  }

  if vim.tbl_contains(format_on_save_servers, client.name) and client.supports_method('textDocument/formatting') then
    local format_group = vim.api.nvim_create_augroup('lsp_format_on_save', { clear = false })
    vim.api.nvim_create_autocmd('BufWritePre', {
      buffer = bufnr,
      group = format_group,
      callback = function() vim.lsp.buf.format({ async = false }) end,
    })
  end
end

-- Configure a single LSP server
function M.setup_server(server_name)
  local ok, config = pcall(require, 'lsp.' .. server_name)
  if not ok then
    vim.notify('Failed to load LSP config for ' .. server_name, vim.log.levels.WARN)
    return
  end

  -- Add common configuration
  config.capabilities = get_default_capabilities()
  config.on_attach = on_attach

  -- Add root_dir function if root_markers exist
  if config.root_markers then
    config.root_dir = function(fname) return vim.fs.dirname(vim.fs.find(config.root_markers, { upward = true, path = fname })[1]) end
    config.root_markers = nil -- Remove after use
  end

  -- Configure the server
  vim.lsp.config(server_name, config)
end

-- Setup all available servers
function M.setup()
  for _, server_name in ipairs(servers) do
    M.setup_server(server_name)
  end

  -- Enable LSP for all configured servers
  vim.lsp.enable()

  vim.notify('Native LSP configured for ' .. #servers .. ' servers', vim.log.levels.INFO)
end

-- Get list of configured servers
function M.get_servers() return vim.deepcopy(servers) end

return M
