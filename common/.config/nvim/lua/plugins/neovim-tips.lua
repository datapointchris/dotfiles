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
    daily_tip = 1,
    -- Bookmark symbol
    bookmark_symbol = '🌟 ',
  },
}
