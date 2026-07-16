return {
  'folke/trouble.nvim',
  dependencies = { 'echasnovski/mini.nvim', 'folke/todo-comments.nvim' }, -- icons via mini.icons mock
  opts = {
    focus = true,
  },
  cmd = 'Trouble',
  keys = {
    { '<leader>xx', '<cmd>Trouble diagnostics toggle filter.buf=0<CR>', desc = 'Trouble buffer diagnostics' },
    { '<leader>xw', '<cmd>Trouble diagnostics toggle<CR>', desc = 'Trouble workspace diagnostics' },
    { '<leader>xq', '<cmd>Trouble quickfix toggle<CR>', desc = 'Trouble quickfix list' },
    { '<leader>xl', '<cmd>Trouble loclist toggle<CR>', desc = 'Trouble location list' },
    { '<leader>xt', '<cmd>Trouble todo toggle<CR>', desc = 'Trouble TODOS' },
  },
}
