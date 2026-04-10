return {
  'folke/which-key.nvim',
  event = 'VeryLazy',
  opts = {
    -- Modern which-key v3 configuration
    preset = 'modern', -- Use modern preset for better appearance
    delay = 5, -- Delay before showing which-key popup
    sort = { 'local', 'order', 'group', 'alphanum', 'mod' }, -- Sort order
    expand = 1, -- Always expand groups (show all items instead of "+X more")

    -- Configure icons (requires mini.icons or nvim-web-devicons)
    icons = {
      mappings = true, -- Enable icons for mappings
      separator = '󰁕', -- Symbol used between key and description
    },
  },
  config = function(_, opts)
    local wk = require('which-key')
    wk.setup(opts)

    -- Add clean, minimal group names without icons
    wk.add({
      -- Main action groups
      { '<leader>a', group = 'AI Chat' },
      { '<leader>c', group = 'AI Assistant' },
      { '<leader>f', group = 'Find & Search' },
      { '<leader>q', group = 'Quit & Exit' },

      -- Code navigation & editing
      { '<leader>l', group = 'Language Server' },
      { '<leader>g', group = 'Go To Location' },
      { '<leader>d', group = 'Document Analysis' },
      { '<leader>w', group = 'Windows & Sessions' },

      -- File & project management
      { '<leader>t', group = 'Tabs' },
      { '<leader>h', group = 'Help & Guides' },

      -- Text manipulation
      { '<leader>y', group = 'Copy to Clipboard' },
      { '<leader>p', group = 'Paste from Clipboard' },

      -- Advanced features
      { '<leader>s', group = 'Screen & Splits' },
      { '<leader>z', group = 'Zen Mode' },
      { '<leader>fm', group = 'Format Code' },
    })
  end,
  keys = {
    {
      '<leader>?',
      function()
        require('which-key').show({
          global = false,
        })
      end,
      desc = 'Buffer Local Keymaps (which-key)',
    },
  },
}
