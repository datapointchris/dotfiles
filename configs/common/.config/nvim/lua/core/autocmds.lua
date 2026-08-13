vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('highlight-yank', { clear = true }),
  callback = function() vim.hl.on_yank() end,
})

vim.api.nvim_create_autocmd('LspAttach', {
  desc = 'LSP: Buffer-local overrides on attach',
  group = vim.api.nvim_create_augroup('lsp_attach_overrides', { clear = true }),
  callback = function(args)
    -- Diffview clears 'buftype' on the index-side buffer so `:w` stages it, and
    -- an empty 'buftype' is the only guard vim.lsp.enable applies. Servers then
    -- attach to a `diffview://…/.git/:0:/file` URI whose directory does not
    -- exist, so nothing resolves and the pane warns on almost every line.
    -- Diffview's own view.*.disable_diagnostics was rejected: it blanks both
    -- panes, so the working-tree side loses its real diagnostics, and it leaves
    -- the client attached to a document that only exists inside .git.
    if vim.api.nvim_buf_get_name(args.buf):find('^diffview://') then
      -- Scheduled because Client:on_attach re-registers the buffer on the line
      -- after it fires LspAttach, so an inline detach is clobbered immediately.
      vim.schedule(function() vim.lsp.buf_detach_client(args.buf, args.data.client_id) end)
      -- Detach only resets pull-based diagnostics; push-based ones would linger.
      vim.diagnostic.enable(false, { bufnr = args.buf })
      return
    end

    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if client == nil then return end
    if client.name == 'ruff' then client.server_capabilities.hoverProvider = false end
    if client.name == 'terraformls' then client.server_capabilities.semanticTokensProvider = nil end
    -- In zk notebooks both marksman and zk attach to markdown. Silence
    -- marksman's hover so zk's note preview (backlinks/link context) wins;
    -- marksman still handles hover for non-note markdown.
    if client.name == 'marksman' then
      local bufname = vim.api.nvim_buf_get_name(args.buf)
      local ok, zk_util = pcall(require, 'zk.util')
      if ok and bufname ~= '' and zk_util.notebook_root(bufname) ~= nil then client.server_capabilities.hoverProvider = false end
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
