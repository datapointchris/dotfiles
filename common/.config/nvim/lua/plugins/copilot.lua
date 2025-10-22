return {
  {
    'zbirenbaum/copilot.lua',
    -- Only load when NVIM_AI_ENABLED is true and not in VSCode
    cond = vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode,
    config = function()
      require('copilot').setup({
        suggestion = {
          enabled = true,
          auto_trigger = true,
          hide_during_completion = true,
          debounce = 75,
          keymap = {
            accept = '<Tab>',
            accept_word = '<C-Right>',
            accept_line = '<C-l>',
            next = '<C-]>',
            prev = '<C-[>',
            dismiss = '<C-e>', -- Dismiss without exiting insert mode
          },
        },
        panel = {
          enabled = false, -- Keep panel disabled, using chat interface
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
