return {
  'linux-cultist/venv-selector.nvim',
  dependencies = {
    'neovim/nvim-lspconfig',
    'mfussenegger/nvim-dap',
    'mfussenegger/nvim-dap-python', -- optional
  },
  lazy = false,
  branch = 'regexp', -- This is the regexp branch, use this for the new version
  keys = { { ',v', '<cmd>VenvSelect<cr>' } },
}
