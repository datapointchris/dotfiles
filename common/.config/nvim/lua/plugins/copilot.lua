return {
  {
    'zbirenbaum/copilot.lua',
    -- Only load when NVIM_AI_ENABLED is true and not in VSCode
    cond = vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode,
    event = 'VimEnter', -- Load earlier to ensure it's ready before InsertEnter
    config = function()
      require('copilot').setup({
        suggestion = {
          enabled = false, -- Disable standalone suggestions, use blink-cmp integration
          auto_trigger = false,
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

  -- blink-cmp-copilot is now configured as a dependency of blink-cmp in blink-cmp.lua

  -- Keep copilot-lualine for status integration
  {
    'AndreM222/copilot-lualine',
    cond = not vim.g.vscode,
  },
}
