return {
  'kdheepak/lazygit.nvim',
  cond = not vim.g.vscode, -- VSCode has excellent built-in Git integration
  cmd = {
    'LazyGit',
    'LazyGitConfig',
    'LazyGitCurrentFile',
    'LazyGitFilter',
    'LazyGitFilterCurrentFile',
  },
  -- optional for floating window border decoration
  dependencies = {
    'nvim-lua/plenary.nvim',
  },
  keys = {
    { '<leader>lg', '<cmd>LazyGit<CR>', desc = 'Open lazygit' },
  },
}
