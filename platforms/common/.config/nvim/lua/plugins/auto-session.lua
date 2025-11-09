return {
  'rmagatti/auto-session',
  lazy = false,
  cond = not vim.g.vscode, -- VSCode doesn't use Neovim sessions
  opts = {
    suppressed_dirs = { '~/', '~/Downloads', '~/Documents', '~/Desktop/', '/' },
    -- log_level = 'debug',
  },
}
