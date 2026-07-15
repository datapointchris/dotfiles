return {
  'sindrets/diffview.nvim',
  opts = {},
  cmd = {
    'DiffviewOpen',
    'DiffviewClose',
    'DiffviewToggleFiles',
    'DiffviewFocusFiles',
    'DiffviewRefresh',
    'DiffviewFileHistory',
  },
  keys = {
    -- DiffviewOpen with no args shows uncommitted changes, and during a merge
    -- it auto-detects the conflict and opens the 3-way resolver.
    { '<leader>gd', '<cmd>DiffviewOpen<cr>', desc = 'Git: diff working tree / resolve conflicts' },
    { '<leader>gh', '<cmd>DiffviewFileHistory %<cr>', desc = 'Git: current file history' },
    { '<leader>gH', '<cmd>DiffviewFileHistory<cr>', desc = 'Git: repo history' },
    { '<leader>gx', '<cmd>DiffviewClose<cr>', desc = 'Git: close diffview' },
  },
}
