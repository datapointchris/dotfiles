return {
  'sindrets/diffview.nvim',
  cond = not vim.g.vscode, -- VSCode has built-in diff viewer
  opts = {},
}
