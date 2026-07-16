vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('highlight-yank', { clear = true }),
  callback = function()
    vim.hl.on_yank()
  end,
})

vim.api.nvim_create_autocmd('LspAttach', {
  desc = 'LSP: Buffer-local overrides on attach',
  group = vim.api.nvim_create_augroup('lsp_attach_overrides', { clear = true }),
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if client == nil then
      return
    end
    if client.name == 'ruff' then
      client.server_capabilities.hoverProvider = false
    end
    if client.name == 'terraformls' then
      client.server_capabilities.semanticTokensProvider = nil
    end
    -- In zk notebooks both marksman and zk attach to markdown. Silence
    -- marksman's hover so zk's note preview (backlinks/link context) wins;
    -- marksman still handles hover for non-note markdown.
    if client.name == 'marksman' then
      local bufname = vim.api.nvim_buf_get_name(args.buf)
      local ok, zk_util = pcall(require, 'zk.util')
      if ok and bufname ~= '' and zk_util.notebook_root(bufname) ~= nil then
        client.server_capabilities.hoverProvider = false
      end
    end
    -- Explicit hover mapping overrides keywordprg (e.g. Python sets pydoc)
    vim.keymap.set('n', 'K', vim.lsp.buf.hover, { buffer = args.buf })
  end,
})

vim.api.nvim_create_autocmd('BufWritePre', {
  desc = 'Run linter on save (except Python to preserve imports while experimenting)',
  group = vim.api.nvim_create_augroup('FixAllOnSave', { clear = true }),
  pattern = '*',
  callback = function()
    -- Skip auto-fixing for Python (preserves unused imports during experimentation)
    -- Python users can manually run <leader>ci when ready to clean up
    if vim.bo.filetype ~= 'python' then
      vim.lsp.buf.code_action({
        context = { only = { 'source.fixAll' }, diagnostics = {} },
        apply = true,
      })
    end
  end,
})
