return {
  {
    'zbirenbaum/copilot.lua',
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
  {
    'AndreM222/copilot-lualine',
  },
}
