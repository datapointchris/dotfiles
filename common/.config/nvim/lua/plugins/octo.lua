return {
  'pwntester/octo.nvim',
  cmd = 'Octo',
  dependencies = {
    'nvim-lua/plenary.nvim',
    'nvim-telescope/telescope.nvim',
    'nvim-tree/nvim-web-devicons',
  },
  config = function()
    require('octo').setup({
      enable_builtin = true,
      use_local_fs = true,
    })
    vim.cmd([[hi OctoEditable guibg=none]])
    vim.treesitter.language.register('markdown', 'octo')
  end,
  keys = {
    { '<leader>O', '<cmd>Octo<cr>', desc = 'Octo' },
    { '<leader>Op', '<cmd>Octo pr list<cr>', desc = 'Octo pr list' },
  },
}
