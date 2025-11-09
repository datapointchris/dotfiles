return {
  'folke/trouble.nvim',
  cond = not vim.g.vscode, -- VSCode has native Problems panel
  dependencies = { 'nvim-tree/nvim-web-devicons', 'folke/todo-comments.nvim' },
  opts = {
    focus = true,
  },
  cmd = 'Trouble',
  keys = {
    { '<leader>xx', '<cmd>Trouble diagnostics toggle filter.buf=0<CR>', desc = 'Trouble buffer diagnostics' },
    { '<leader>xw', '<cmd>Trouble diagnostics toggle<CR>', desc = 'Trouble workspace diagnostics' },
    {
      '<leader>xd',
      '<cmd>Trouble diagnostics toggle filter.buf=0<CR>',
      desc = 'Trouble document diagnostics',
    },
    { '<leader>xq', '<cmd>Trouble quickfix toggle<CR>', desc = 'Trouble quickfix list' },
    { '<leader>xl', '<cmd>Trouble loclist toggle<CR>', desc = 'Trouble location list' },
    { '<leader>xt', '<cmd>Trouble todo toggle<CR>', desc = 'Trouble TODOS' },
  },
}
