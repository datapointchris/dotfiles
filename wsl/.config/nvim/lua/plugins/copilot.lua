return {
  {
    'zbirenbaum/copilot.lua',
    cond = not vim.g.vscode, -- VSCode has native Copilot integration
    config = function()
      require('copilot').setup({
        suggestion = {
          enabled = false,
        },
        panel = {
          enabled = false,
        },
      })
    end,
  },
  {
    'zbirenbaum/copilot-cmp',
    cond = not vim.g.vscode, -- VSCode has native Copilot integration
    config = function() require('copilot_cmp').setup() end,
  },
  { 'AndreM222/copilot-lualine' },
}
