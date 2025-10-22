return {
  {
    'zbirenbaum/copilot.lua',
    cond = not vim.g.vscode, -- VSCode has native Copilot integration
    config = function()
      require('copilot').setup({
        suggestion = {
          enabled = false, -- Disabled in favor of CodeCompanion chat interface
        },
        panel = {
          enabled = false, -- Using CodeCompanion chat buffer instead
        },
        -- Keep copilot running for CodeCompanion adapter
        server_opts_overrides = {
          trace = 'verbose', -- Help debug any issues
        },
      })
    end,
  },

  -- Disable copilot-cmp since we're using native LSP completion + CodeCompanion
  {
    'zbirenbaum/copilot-cmp',
    enabled = false, -- Conflicts with native LSP completion
    cond = false,
  },

  -- Keep copilot-lualine for status integration
  {
    'AndreM222/copilot-lualine',
    cond = not vim.g.vscode,
  },
}
