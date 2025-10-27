return {
  'saxon1964/neovim-tips',
  version = '*', -- Only update on tagged releases
  dependencies = {
    'MunifTanjim/nui.nvim',
    -- Use existing render-markdown.nvim for markdown rendering
    'MeanderingProgrammer/render-markdown.nvim',
  },
  opts = {
    -- Location of user defined tips
    user_file = vim.fn.stdpath('config') .. '/neovim_tips/user_tips.md',
    -- Prefix for user tips to avoid conflicts
    user_tip_prefix = '[User] ',
    -- Show warnings when user tips conflict with builtin
    warn_on_conflicts = true,
    -- Daily tip mode: 0=off, 1=once per day, 2=every startup
    daily_tip = 2,
    -- Bookmark symbol
    bookmark_symbol = '🌟 ',
  },
  cmd = {
    'NeovimTips',
    'NeovimTipsEdit',
    'NeovimTipsAdd',
    'NeovimTipsRandom',
    'NeovimTipsPdf',
  },
  keys = {
    { '<leader>nt', '', desc = 'Neovim Tips' },
    { '<leader>nto', '<cmd>NeovimTips<CR>', desc = 'Open Neovim tips' },
    { '<leader>nte', '<cmd>NeovimTipsEdit<CR>', desc = 'Edit your Neovim tips' },
    { '<leader>nta', '<cmd>NeovimTipsAdd<CR>', desc = 'Add your Neovim tip' },
    { '<leader>nth', '<cmd>help neovim-tips<CR>', desc = 'Neovim tips help' },
    { '<leader>ntr', '<cmd>NeovimTipsRandom<CR>', desc = 'Show random tip' },
    { '<leader>ntp', '<cmd>NeovimTipsPdf<CR>', desc = 'Open Neovim tips PDF' },
  },
}
