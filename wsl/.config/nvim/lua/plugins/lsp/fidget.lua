-- https://github.com/j-hui/fidget.nvim

-- Fidget is an unintrusive window in the corner of your editor that manages its own lifetime. Its goals are:

-- to provide a UI for Neovim's $/progress handler
-- to provide a configurable vim.notify() backend
-- to support basic ASCII animations (Fidget spinners!) to indicate signs of life

return {
  'j-hui/fidget.nvim',
  cond = not vim.g.vscode, -- VSCode has its own progress indicators
  opts = {},
}
