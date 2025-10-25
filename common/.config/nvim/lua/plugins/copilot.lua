return {
  {
    'zbirenbaum/copilot.lua',
    -- Only load when NVIM_AI_ENABLED is true and not in VSCode
    cond = vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode,
    config = function()
      require('copilot').setup({
        suggestion = {
          enabled = false, -- Disable standalone suggestions, use nvim-cmp integration
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

  -- Enable copilot-cmp for unified completion in nvim-cmp
  {
    'zbirenbaum/copilot-cmp',
    enabled = true, -- Re-enabled for unified completion experience
    cond = vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode,
    config = function()
      require('copilot_cmp').setup()
    end,
  },

  -- Keep copilot-lualine for status integration
  {
    'AndreM222/copilot-lualine',
    cond = not vim.g.vscode,
  },
}
