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

        -- Inspect (hunk staging is handled by lazygit; file diffs by diffview)
        map('n', '<leader>gp', gitsigns.preview_hunk, {
          desc = 'git [p]review hunk',
        })
        map('n', '<leader>gb', gitsigns.blame_line, {
          desc = 'git [b]lame line',
        })
        -- Toggles
        map('n', '<leader>gtb', gitsigns.toggle_current_line_blame, {
          desc = 'git: [t]oggle [b]lame line',
        })
        map('n', '<leader>gtd', gitsigns.toggle_deleted, {
          desc = 'git: [t]oggle [d]eleted',
        })
      end,
    },
  },
}
