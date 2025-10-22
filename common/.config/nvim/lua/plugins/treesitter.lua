return {
  'nvim-treesitter/nvim-treesitter',
  build = ':TSUpdate',
  event = { 'BufReadPre', 'BufNewFile' },
  dependencies = {
    'nvim-treesitter/nvim-treesitter-textobjects',
  },
  config = function()
    local configs = require('nvim-treesitter.configs')

    configs.setup({
      auto_install = true,
      sync_install = false,
      highlight = { enable = true },
      indent = { enable = true },
      ensure_installed = {},
      ignore_install = {},
      modules = {},
      incremental_selection = {
        enable = true,
        keymaps = {
          init_selection = '<leader>gnn',
          node_incremental = '<leader>grn',
          scope_incremental = '<leader>grc',
          node_decremental = '<leader>grm',
        },
      },
    })
  end,
}
