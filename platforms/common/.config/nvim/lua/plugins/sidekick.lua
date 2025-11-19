-- sidekick.nvim - Next Edit Suggestions (NES)
-- Purpose: Copilot multi-line completions (like GitHub Copilot "ghost text" but better)
--
-- Keybindings:
--   <Tab> - Accept NES suggestion
--   <S-Tab> - Cycle through suggestions
--   <leader>ne - Toggle NES on/off

return {
  'folke/sidekick.nvim',
  event = 'VeryLazy',
  dependencies = { 'zbirenbaum/copilot.lua' },
  opts = {
    -- Next Edit Suggestions - Copilot multi-line completions
    nes = {
      enabled = true,
      provider = 'copilot', -- Use Copilot for suggestions
    },

    -- Disable CLI (use tmux/floaterminal instead)
    cli = {
      enabled = false,
    },
  },

  keys = {
    {
      '<Tab>',
      function()
        require('sidekick').nes_jump_or_apply()
      end,
      desc = 'NES: Accept/jump',
      mode = { 'i', 'n' },
    },
    { '<leader>ne', '<cmd>Sidekick nes toggle<cr>', desc = 'NES: Toggle', mode = 'n' },
  },
}
