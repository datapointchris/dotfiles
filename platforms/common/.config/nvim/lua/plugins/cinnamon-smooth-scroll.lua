return {
  'declancm/cinnamon.nvim',
  cond = not vim.g.vscode, -- VS Code handles scrolling
  version = '*', -- use latest release
  opts = {
    keymaps = {
      basic = true,
      extra = true,
      delay = 2,
    },
  },
}
