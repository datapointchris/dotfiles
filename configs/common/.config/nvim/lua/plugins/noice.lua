-- Messages and cmdline UI. The command_palette preset is what puts `:` in a
-- centred box with the completion menu attached beneath it; bottom_search keeps
-- `/` and `?` on the last line, where incsearch context is readable.
--
-- noice takes ext_messages, which implies ext_cmdline, so it cannot run beside
-- Neovim's native ui2 — enabling both leaves two attached UIs fighting over the
-- same events.
return {
  'folke/noice.nvim',
  event = 'VeryLazy',
  dependencies = {
    'MunifTanjim/nui.nvim',
  },
  opts = {
    -- fidget is the vim.notify backend (plugins/fidget.lua).
    notify = { enabled = false },
    lsp = {
      progress = { enabled = false },
      override = {
        ['vim.lsp.util.convert_input_to_markdown_lines'] = true,
        ['vim.lsp.util.stylize_markdown'] = true,
        ['cmp.entry.get_documentation'] = true,
      },
    },
    routes = {
      { filter = { event = 'msg_show', min_height = 10 }, view = 'split' },
      { filter = { event = 'msg_show', kind = 'error' }, opts = { timeout = 10000 } },
      { filter = { event = 'msg_show', kind = 'warn' }, opts = { timeout = 7000 } },
    },
    presets = {
      bottom_search = true,
      command_palette = true,
      long_message_to_split = true,
      inc_rename = true,
      lsp_doc_border = true,
    },
  },
  config = function(_, opts)
    require('noice').setup(opts)

    -- parse_event splits an event name on its underscore, so a UI event without
    -- one ("restart", added in 0.12) yields nil and the caller concatenates it.
    -- Every dispatch path guards on get_handler first, but the skipped-event
    -- stats counter does not.
    local ui = require('noice.ui')
    local parse_event = ui.parse_event
    ui.parse_event = function(event)
      local group, kind = parse_event(event)
      return group or event, kind or ''
    end
  end,
}
