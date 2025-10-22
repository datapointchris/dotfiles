return {
  'akinsho/bufferline.nvim',
  version = '*',
  cond = not vim.g.vscode, -- VSCode handles tabs natively
  dependencies = 'nvim-tree/nvim-web-devicons',
}
