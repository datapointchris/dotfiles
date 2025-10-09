return {
  {
    'olimorris/codecompanion.nvim',
    dependencies = {
      'nvim-lua/plenary.nvim',
      'nvim-treesitter/nvim-treesitter',
      'echasnovski/mini.diff',
      'j-hui/fidget.nvim',
    },
    opts = {
      strategies = {
        chat = {
          adapter = {
            name = 'copilot',
            model = 'claude sonnet 4',
          },
        },
        {
          inline = {
            adapter = {
              name = 'copilot',
              model = 'claude sonnet 4',
            },
          },
        },
        display = {
          action_palette = {
            provider = 'telescope',
          },
          diff = {
            provider = 'mini_diff',
          },
        },
      },
    },
  },
  {
    'echasnovski/mini.diff', -- Inline and better diff over the default
    config = function()
      local diff = require('mini.diff')
      diff.setup({
        -- Disabled by default
        source = diff.gen_source.none(),
      })
    end,
  },
}
