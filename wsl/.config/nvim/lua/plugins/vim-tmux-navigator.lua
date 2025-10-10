return {
  'christoomey/vim-tmux-navigator',
  cond = not vim.g.vscode, -- VSCode uses workbench navigation
  cmd = {
    'TmuxNavigateLeft',
    'TmuxNavigateDown',
    'TmuxNavigateUp',
    'TmuxNavigateRight',
    'TmuxNavigatePrevious',
  },
}
