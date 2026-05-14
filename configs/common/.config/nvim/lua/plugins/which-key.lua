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

    -- Group labels for which-key popup. Goal: every prefix with real keymaps
    -- has an accurate label; nothing is registered that has no bindings.
    wk.add({
      -- AI / chat
      { '<leader>c', group = 'AI Assistant (CodeCompanion)' },

      -- Find / search
      { '<leader>f', group = 'Find & Search (Telescope)' },
      { '<leader>fm', group = 'Format Code' },

      -- LSP / code navigation
      { '<leader>l', group = 'LSP' },
      { '<leader>g', group = 'Go To / Treesitter' },
      { '<leader>d', group = 'Document Symbols' },
      { '<leader>x', group = 'Trouble Diagnostics' },

      -- Git
      { '<leader>h', group = 'Git Hunks' },
      { '<leader>ht', group = 'Git Toggles' },

      -- Buffers / windows / sessions
      { '<leader>t', group = 'Tabs' },
      { '<leader>w', group = 'Windows & Sessions' },
      { '<leader>r', group = 'Reload Config' },

      -- Quit
      { '<leader>q', group = 'Quit & Exit' },

      -- Editing / clipboard
      { '<leader>y', group = 'Yank to Clipboard' },
      { '<leader>p', group = 'Paste from Clipboard' },
      { '<leader>n', group = 'Noice / Notifications' },
      { '<leader>s', group = 'Swap (Treesitter)' },
      { '<leader>sn', group = 'Swap with Next' },
      { '<leader>sp', group = 'Swap with Previous' },

      -- Tools
      { '<leader>b', group = 'Debug Breakpoints (DAP)' },
      { '<leader>m', group = 'Molten (Jupyter)' },
      { '<leader>O', group = 'Octo (GitHub PRs)' },
      { '<leader>z', group = 'Zen Mode & ZK Notes' },
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
