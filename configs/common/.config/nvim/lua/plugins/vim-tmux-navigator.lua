return {
  'christoomey/vim-tmux-navigator',
  cmd = {
    'TmuxNavigateLeft',
    'TmuxNavigateDown',
    'TmuxNavigateUp',
    'TmuxNavigateRight',
    'TmuxNavigatePrevious',
  },
  init = function()
    vim.g.tmux_navigator_no_mappings = 1
  end,
  keys = {
    { '<C-Left>', '<cmd>TmuxNavigateLeft<cr>', desc = 'Navigate pane left' },
    { '<C-Down>', '<cmd>TmuxNavigateDown<cr>', desc = 'Navigate pane down' },
    { '<C-Up>', '<cmd>TmuxNavigateUp<cr>', desc = 'Navigate pane up' },
    { '<C-Right>', '<cmd>TmuxNavigateRight<cr>', desc = 'Navigate pane right' },
  },
}
