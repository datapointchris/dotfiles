-- Trialled alongside diffview.nvim. Both are installed on purpose: diffbandit
-- keeps each side's original formatting and draws the relationships in a
-- connector gutter instead of padding both buffers with filler lines, so the
-- two are worth using side by side before picking one.
return {
  'CoreyKaylor/diffbandit.nvim',
  opts = {},
  cmd = {
    'DiffBandit',
    'DiffBanditBuffers',
    'DiffBanditFolderDiff',
    'DiffBanditGit',
    'DiffBanditGitCurrent',
    'DiffBanditGitLog',
    'DiffBanditGitCommit',
    'DiffBanditGitCompare',
    'DiffBanditGitCheckout',
    'DiffBanditGitMenu',
    'DiffBanditCommitPanel',
    'DiffBanditMerge',
  },
  keys = {
    { '<leader>gBd', '<cmd>DiffBanditGit<cr>', desc = 'DiffBandit: changed files' },
    { '<leader>gBf', '<cmd>DiffBanditGitCurrent<cr>', desc = 'DiffBandit: current file diff' },
    { '<leader>gBl', '<cmd>DiffBanditGitLog<cr>', desc = 'DiffBandit: commit log' },
    { '<leader>gBc', '<cmd>DiffBanditCommitPanel<cr>', desc = 'DiffBandit: commit panel' },
    { '<leader>gBm', '<cmd>DiffBanditGitMenu<cr>', desc = 'DiffBandit: git menu' },
  },
}
