-- lazy.nvim
return {
  'folke/noice.nvim',
  event = 'VeryLazy',
  dependencies = {
    'MunifTanjim/nui.nvim',
  },
  opts = {
    lsp = {
      -- Let Fidget handle LSP progress messages
      progress = {
        enabled = false,
      },
      override = {
        ['vim.lsp.util.convert_input_to_markdown_lines'] = true,
        ['vim.lsp.util.stylize_markdown'] = true,
        ['cmp.entry.get_documentation'] = true,
      },
    },
    routes = {
      -- Route long messages to split view
      {
        filter = {
          event = 'msg_show',
          min_height = 10,
        },
        view = 'split',
      },
      -- Keep errors visible longer
      {
        filter = {
          event = 'msg_show',
          kind = 'error',
        },
        opts = { timeout = 10000 }, -- 10 seconds for errors
      },
      -- Keep warnings visible longer
      {
        filter = {
          event = 'msg_show',
          kind = 'warn',
        },
        opts = { timeout = 7000 }, -- 7 seconds for warnings
      },
    },
    presets = {
      bottom_search = true, -- Use classic bottom search
      command_palette = true, -- Position cmdline and popupmenu together
      long_message_to_split = true, -- Long messages sent to split
      inc_rename = false, -- Enable input dialog for inc-rename.nvim
      lsp_doc_border = true, -- Add border to hover docs and signature help
    },
    views = {
      notify = {
        replace = false, -- Don't replace existing notifications
      },
    },
  },
  keys = {
    -- Keymap to search through all messages with Telescope
    {
      '<leader>fmm',
      '<cmd>Telescope noice<cr>',
      desc = 'Search Noice Messages',
    },
    -- Keymap to show message history
    {
      '<leader>fmh',
      '<cmd>Noice history<cr>',
      desc = 'Noice History',
    },
    -- Keymap to dismiss all visible notifications
    {
      '<leader>nd',
      '<cmd>Noice dismiss<cr>',
      desc = 'Dismiss Noice Notifications',
    },
  },
}
