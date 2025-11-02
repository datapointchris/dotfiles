-- https://github.com/j-hui/fidget.nvim

-- Fidget is an unintrusive window in the corner of your editor that manages its own lifetime. Its goals are:

-- to provide a UI for Neovim's $/progress handler
-- to provide a configurable vim.notify() backend
-- to support basic ASCII animations (Fidget spinners!) to indicate signs of life

return {
  'j-hui/fidget.nvim',
  cond = not vim.g.vscode, -- VSCode has its own progress indicators
  opts = {
    progress = {
      display = {
        render_limit = 16, -- How many LSP messages to show at once
        done_ttl = 3, -- How long a message should persist after completion
        done_icon = '✔', -- Icon shown when all tasks are complete
      },
    },
    notification = {
      override_vim_notify = false, -- Let Noice handle vim.notify() instead
      window = {
        winblend = 0, -- Background transparency (0 = opaque)
        border = 'rounded',
      },
    },
  },
}
