return {
  'smjonas/inc-rename.nvim',
  cond = not vim.g.vscode, -- Depends on dressing.nvim (disabled in vscode)
  config = function()
    require('inc_rename').setup({
      input_buffer_type = 'dressing',
    })
  end,
}
