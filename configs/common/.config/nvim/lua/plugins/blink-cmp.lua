-- Blink.cmp - Fast and feature-rich completion plugin
-- Documentation: https://cmp.saghen.dev

return {
  'saghen/blink.cmp',
  -- V2 build/download system: :pwait() fetches the prebuilt native fuzzy
  -- library (or builds it if unsupported). The old :wait(timeout) form is
  -- deprecated in V2 and triggers a startup warning + falls back to the
  -- slower Lua matcher.
  build = function()
    require('blink.cmp').build():pwait()
  end,
  dependencies = {
    'saghen/blink.lib',
    'rafamadriz/friendly-snippets',
  },

  opts = function()
    local default_sources = { 'lsp', 'path', 'snippets', 'buffer', 'lazydev' }

    return {
      enabled = function()
        return not vim.tbl_contains({ 'TelescopePrompt', 'markdown', 'text' }, vim.bo.filetype)
      end,
      keymap = {
        preset = 'none',
        ['<C-space>'] = { 'show', 'show_documentation', 'hide_documentation' },
        ['<C-e>'] = { 'hide' },
        ['<C-n>'] = { 'select_next', 'fallback' },
        ['<C-p>'] = { 'select_prev', 'fallback' },
        ['<Tab>'] = { 'select_and_accept', 'snippet_forward', 'fallback' },
        ['<S-Tab>'] = { 'snippet_backward', 'fallback' },
        ['<C-j>'] = { 'scroll_documentation_down', 'fallback' },
        ['<C-k>'] = { 'scroll_documentation_up', 'fallback' },
        ['<C-;>'] = { 'show', 'fallback' }, -- Manual trigger
      },

      appearance = {
        nerd_font_variant = 'mono',
        kind_icons = {
          Text = '󰉿',
          Method = '󰊕',
          Function = '󰊕',
          Constructor = '󰒓',
          Field = '󰜢',
          Variable = '󰆦',
          Property = '󰖷',
          Class = '󱡠',
          Interface = '󱡠',
          Struct = '󱡠',
          Module = '󰅩',
          Unit = '󰪚',
          Value = '󰦨',
          Enum = '󰦨',
          EnumMember = '󰦨',
          Keyword = '󰻾',
          Constant = '󰏿',
          Snippet = '󱄽',
          Color = '󰏘',
          File = '󰈔',
          Reference = '󰬲',
          Folder = '󰉋',
          Event = '󱐋',
          Operator = '󰪚',
          TypeParameter = '󰬛',
        },
      },

      completion = {
        keyword = {
          range = 'full', -- Match before and after cursor
        },
        trigger = {
          prefetch_on_insert = true,
          show_in_snippet = true,
          show_on_keyword = true,
          show_on_trigger_character = true,
        },
        list = {
          max_items = 200,
          selection = {
            preselect = true,
            auto_insert = true,
          },
        },
        accept = {
          auto_brackets = {
            enabled = false,
          },
        },
        menu = {
          -- border omitted: blink falls back to the global 'winborder' when
          -- unset (nvim 0.11+), so no per-window border is needed here.
          draw = {
            columns = {
              { 'kind_icon' },
              { 'label', 'label_description', gap = 1 },
              { 'source_name' },
            },
          },
        },
        documentation = {
          auto_show = true,
          auto_show_delay_ms = 200,
          -- window.border omitted: inherits the global 'winborder'
        },
        ghost_text = {
          enabled = false, -- No inline ghost text; use the completion menu only
        },
      },

      -- fuzzy = {
      --   -- Using default fuzzy settings
      -- },

      sources = {
        default = default_sources,

        providers = {
          lazydev = {
            name = 'LazyDev',
            module = 'lazydev.integrations.blink',
            score_offset = 100, -- Prioritize lazydev completions for Lua
          },
          lsp = {
            name = 'LSP',
            module = 'blink.cmp.sources.lsp',
          },
          path = {
            name = 'Path',
            module = 'blink.cmp.sources.path',
            opts = {
              trailing_slash = false,
              label_trailing_slash = true,
              get_cwd = function(context)
                return vim.fn.expand(('#%d:p:h'):format(context.bufnr))
              end,
              show_hidden_files_by_default = true,
            },
          },
          snippets = {
            name = 'Snippets',
            module = 'blink.cmp.sources.snippets',
            opts = {
              friendly_snippets = true,
              search_paths = { vim.fn.stdpath('config') .. '/snippets' },
            },
          },
          buffer = {
            name = 'Buffer',
            module = 'blink.cmp.sources.buffer',
            opts = {
              -- Only search visible buffers
              get_bufnrs = function()
                local bufs = {}
                for _, win in ipairs(vim.api.nvim_list_wins()) do
                  bufs[vim.api.nvim_win_get_buf(win)] = true
                end
                return vim.tbl_keys(bufs)
              end,
            },
          },
        },
      },

      signature = {
        enabled = true,
        -- window.border omitted: inherits the global 'winborder'
      },
    }
  end,

  opts_extend = { 'sources.default' },
}
