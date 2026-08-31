return {
  'sindrets/diffview.nvim',
  opts = {
    -- Vim's diff engine marks a line that exists on the left and not the right
    -- as DiffAdd *in the left pane*, so a deletion reads green without this.
    -- The remap is per-window: the left pane's DiffAdd becomes
    -- DiffviewDiffAddAsDelete, which copies DiffDelete, and the filler rows on
    -- both sides become DiffviewDiffDeleteDim, which links Comment and so
    -- carries no background. Paired with 'fillchars' diff:' ' in core.diff,
    -- that leaves a removed region blank rather than a red rule.
    enhanced_diff_hl = true,
  },
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
