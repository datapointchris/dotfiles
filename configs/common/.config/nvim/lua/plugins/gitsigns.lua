-- Adds git related signs to the gutter, as well as utilities for managing changes
return {
  {
    'lewis6991/gitsigns.nvim',
    opts = {
      on_attach = function(bufnr)
        local gitsigns = require('gitsigns')

        local function map(mode, l, r, opts)
          opts = opts or {}
          opts.buffer = bufnr
          vim.keymap.set(mode, l, r, opts)
        end

        -- Navigation
        map('n', ']c', function()
          if vim.wo.diff then
            vim.cmd.normal({
              ']c',
              bang = true,
            })
          else
            gitsigns.nav_hunk('next')
          end
        end, {
          desc = 'Jump to next git [c]hange',
        })

        map('n', '[c', function()
          if vim.wo.diff then
            vim.cmd.normal({
              '[c',
              bang = true,
            })
          else
            gitsigns.nav_hunk('prev')
          end
        end, {
          desc = 'Jump to previous git [c]hange',
        })

        -- Actions
        map('n', '<leader>hp', gitsigns.preview_hunk, {
          desc = 'git [p]review hunk',
        })
        map('n', '<leader>hb', gitsigns.blame_line, {
          desc = 'git [b]lame line',
        })
        map('n', '<leader>hd', gitsigns.diffthis, {
          desc = 'git [d]iff against index',
        })
        map('n', '<leader>hD', function()
          gitsigns.diffthis('@')
        end, {
          desc = 'git [D]iff against last commit',
        })
        -- Toggles (grouped under git-hunks prefix)
        map('n', '<leader>htb', gitsigns.toggle_current_line_blame, {
          desc = 'git: [T]oggle [b]lame line',
        })
        map('n', '<leader>htd', gitsigns.toggle_deleted, {
          desc = 'git: [T]oggle [d]eleted',
        })
      end,
    },
  },
}
