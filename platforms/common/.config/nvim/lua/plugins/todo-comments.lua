return {
  'folke/todo-comments.nvim',
  cond = not vim.g.vscode, -- VS Code has todo-tree extension
  event = 'VimEnter',
  dependencies = { 'nvim-lua/plenary.nvim' },
  opts = {
    signs = false,
  },
}
