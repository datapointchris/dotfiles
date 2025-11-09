return {
  'stevearc/dressing.nvim',
  event = 'VeryLazy',
  cond = not vim.g.vscode, -- VSCode has native input dialogs
}
