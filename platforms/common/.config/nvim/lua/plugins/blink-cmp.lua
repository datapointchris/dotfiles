-- Blink.cmp - Fast and feature-rich completion plugin
-- Documentation: https://cmp.saghen.dev

return {
  'saghen/blink.cmp',
  version = '0.*',
  cond = not vim.g.vscode,
  dependencies = {
    'rafamadriz/friendly-snippets',
    {
      'giuxtaposition/blink-cmp-copilot',
      cond = vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode,
    },
  },

  opts = function()
    -- Build sources list conditionally based on environment
    local default_sources = { 'lsp', 'path', 'snippets', 'buffer', 'lazydev' }

    -- Only add copilot if AI is enabled and not in VSCode
    if vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode then table.insert(default_sources, 'copilot') end

    return {
      enabled = function() return not vim.tbl_contains({ 'TelescopePrompt', 'markdown', 'text' }, vim.bo.filetype) end,
      -- Keymap configuration
      keymap = {
        preset = 'none', -- We'll define custom keymaps
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
          Copilot = '',
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
            enabled = true,
          },
        },
        menu = {
          border = 'rounded',
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
          window = {
            border = 'rounded',
          },
        },
        ghost_text = {
          enabled = false, -- Disable inline ghost text, use completion menu
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
          copilot = {
            name = 'copilot',
            module = 'blink-cmp-copilot',
            score_offset = 100, -- Prioritize Copilot suggestions
            async = true,
            enabled = function() return vim.env.NVIM_AI_ENABLED == 'true' and not vim.g.vscode end,
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
              get_cwd = function(context) return vim.fn.expand(('#%d:p:h'):format(context.bufnr)) end,
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
        window = {
          border = 'rounded',
        },
      },
    }
  end,

  opts_extend = { 'sources.default' },
}
