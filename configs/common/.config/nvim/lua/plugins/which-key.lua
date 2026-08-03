return {
  'folke/which-key.nvim',
  event = 'VeryLazy',
  opts = {
    -- Modern which-key v3 configuration
    preset = 'modern', -- Use modern preset for better appearance
    delay = 5, -- Delay before showing which-key popup
    sort = { 'local', 'order', 'group', 'alphanum', 'mod' }, -- Sort order
    expand = 1, -- Auto-expand groups with <= 1 child

    -- The 'modern' preset caps the popup at 25 rows; raise it so the full
    -- <leader>? listing fits on screen (scroll keys are <c-d>/<c-u>, but they
    -- only engage when content overflows the window).
    win = {
      height = { min = 4, max = 0.75 },
    },

    -- Icons are visual clutter here, so turn them all off. `mappings = false`
    -- stops per-keymap icons; empty `keys` stops the special-key glyphs
    -- (<Space>, <CR>, etc.) from being swapped for symbols.
    icons = {
      mappings = false, -- No icons next to each mapping
      keys = {}, -- Don't substitute key names with icon glyphs
      separator = '󰁕', -- Symbol used between key and description
    },
  },
  config = function(_, opts)
    local wk = require('which-key')
    wk.setup(opts)

    -- Group labels for which-key popup. Goal: every prefix with real keymaps
    -- has an accurate label; nothing is registered that has no bindings.
    wk.add({
      -- Code / format / rename
      { '<leader>c', group = 'Code' },

      -- Find / search
      { '<leader>f', group = 'Find & Search (Telescope)' },

      -- LSP / code navigation
      { '<leader>l', group = 'LSP' },
      { '<leader>x', group = 'Trouble Diagnostics' },

      -- Git
      { '<leader>g', group = 'Git' },
      { '<leader>gt', group = 'Git Toggles' },
      { '<leader>gB', group = 'DiffBandit' },

      -- Buffers / windows / sessions
      { '<leader>b', group = 'Buffers' },
      { '<leader>t', group = 'Tabs & Terminal' },
      { '<leader>w', group = 'Windows & Sessions' },
      { '<leader>r', group = 'Reload Config' },

      -- Quit
      { '<leader>q', group = 'Quit & Exit' },

      -- Notifications / treesitter
      { '<leader>n', group = 'Notifications / Messages' },
      { '<leader>s', group = 'Treesitter (Select & Swap)' },
      { '<leader>sn', group = 'Swap with Next' },
      { '<leader>sp', group = 'Swap with Previous' },

      -- Tools
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
