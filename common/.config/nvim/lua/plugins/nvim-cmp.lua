-- cmp is the completion engine
-- -- cmp_luasnip is for running LuaSnip with cmp
-- -- LuaSnip is the snippet Engine for neovim
-- -- -- friendly-snippets is a collection of snippets that can be used by LuaSnip

-- cmp-nvim-lsp is the completion source for nvim-lsp to get completions from the LSP
-- cmp-path is the completion source for path
-- cmp-buffer is the completion source for buffer
-- cmp-copilot is the completion source for copilot (in the copilot file)
-- lazydev

-- # Core Components:
-- nvim-cmp: This is the completion engine itself. It's essential for providing the completion framework.
-- LuaSnip: A popular snippet engine for Neovim. It allows you to define and use snippets, which are boilerplate templates for coding faster.

-- # Snippet Related:
-- friendly-snippets: A repository of pre-defined snippets for various languages, useful if you want out-of-the-box snippets.
-- cmp_luasnip: This is required to use LuaSnip snippets within the nvim-cmp completion.

-- # Completion Sources:
-- cmp-nvim-lsp: Provides completions sourced from LSP (Language Server Protocol) servers. Essential if you want completions from your configured LSPs.
-- cmp-path: Offers file path completions. Useful if you frequently work with files and directories.
-- cmp-buffer: Sources completions from the current buffer. Useful if you want to reuse text from your current file.

-- # Optional/Specific Needs:
-- cmp-copilot: Integrates GitHub Copilot suggestions into nvim-cmp. Keep this if you actively use Copilot.
-- lazydev:

return {
  'hrsh7th/nvim-cmp',
  event = { 'InsertEnter', 'CmdlineEnter' },
  cond = not vim.g.vscode, -- VSCode has native IntelliSense and completion
  dependencies = { -- Snippet Engine & its associated nvim-cmp source
    'brenoprata10/nvim-highlight-colors', -- highlight colors for completion items
    'saadparwaiz1/cmp_luasnip', -- running LuaSnip with cmp
    'hrsh7th/cmp-nvim-lsp', -- completions from LSP
    'onsails/lspkind.nvim', -- icons for completion items
    'hrsh7th/cmp-buffer', -- completions from buffer
    'hrsh7th/cmp-path', -- completions from path
    'zbirenbaum/copilot-cmp', -- copilot completions integrated with nvim-cmp
    {
      'L3MON4D3/LuaSnip',
      version = 'v2.*', -- follow latest release.
      build = 'make install_jsregexp', -- install jsregexp (optional!).
      dependencies = {
        {
          'rafamadriz/friendly-snippets',
          config = function()
            require('luasnip.loaders.from_vscode').lazy_load()
          end,
        },
      },
    },
    {
      'nvimdev/lspsaga.nvim', -- Better UI for LSP -- https://nvimdev.github.io/lspsaga/
      config = function()
        require('lspsaga').setup({ ui = { code_action = '' } })
      end,
      dependencies = { 'nvim-treesitter/nvim-treesitter', 'nvim-tree/nvim-web-devicons' },
    },
  },
  config = function()
    local luasnip = require('luasnip')
    luasnip.config.setup({
      enable_autosnippets = true,
      store_selection_keys = '<Tab>',
    })

    local cmp = require('cmp')
    cmp.setup({
      enabled = function()
        local buftype = vim.bo.buftype
        local filetype = vim.bo.filetype

        -- Disable in prompt buffers (Telescope, etc)
        if buftype == 'prompt' then
          return false
        end

        -- Disable for markdown files
        if filetype == 'markdown' then
          return false
        end

        return true
      end,
      performance = {
        debounce = 150, -- Delay before triggering completion after typing stops
        throttle = 60, -- Limit how often completion can trigger
        fetching_timeout = 200, -- Timeout for completion sources
        max_view_entries = 5, -- Limit number of completion items shown
        async_budget = 1, -- Time budget for async operations
        confirm_resolve_timeout = 80, -- Timeout for resolving completion items on confirm
        filtering_context_budget = 3, -- Time budget for filtering context
      },
      snippet = {
        expand = function(args)
          luasnip.lsp_expand(args.body)
        end,
      },
      completion = {
        completeopt = 'menu,menuone,noinsert,noselect',
        keyword_length = 2, -- Require at least 2 characters before triggering
      },
      formatting = {
        format = function(entry, item)
          local color_item = require('nvim-highlight-colors').format(entry, { kind = item.kind })
          item = require('lspkind').cmp_format({
            -- any lspkind format settings here
          })(entry, item)
          if color_item.abbr_hl_group then
            item.kind_hl_group = color_item.abbr_hl_group
            item.kind = color_item.abbr
          end
          return item
        end,
        expandable_indicator = true,
      },
      sources = {
        { name = 'lazydev', group_index = 1 },
        { name = 'nvim_lsp', group_index = 1 },
        { name = 'copilot', group_index = 0 },
        { name = 'luasnip', group_index = 2 },
        {
          name = 'buffer',
          group_index = 2,
          option = {
            -- Only search visible buffers for completions
            get_bufnrs = function()
              local bufs = {}
              for _, win in ipairs(vim.api.nvim_list_wins()) do
                bufs[vim.api.nvim_win_get_buf(win)] = true
              end
              return vim.tbl_keys(bufs)
            end,
          },
        },
        { name = 'path', group_index = 2 },
      },
      mapping = {
        ['<C-j>'] = cmp.mapping.scroll_docs(-4),
        ['<C-k>'] = cmp.mapping.scroll_docs(4),

        -- Alternative: Ctrl+E to dismiss completion (stays in insert mode)
        ['<C-e>'] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.close()
            -- Stay in insert mode
          else
            fallback()
          end
        end, { 'i' }),

        ['<Tab>'] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.confirm({
              behavior = cmp.ConfirmBehavior.Replace,
              select = true,
            })
          elseif luasnip.locally_jumpable(1) then
            luasnip.jump(1)
          else
            fallback()
          end
        end, { 'i', 's' }),

        ['<C-n>'] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.select_next_item()
          elseif luasnip.locally_jumpable(1) then
            luasnip.jump(1)
          else
            fallback()
          end
        end, { 'i', 's' }),

        ['<C-p>'] = cmp.mapping(function(fallback)
          if cmp.visible() then
            cmp.select_prev_item()
          elseif luasnip.locally_jumpable(-1) then
            luasnip.jump(-1)
          else
            fallback()
          end
        end, { 'i', 's' }),

        -- Manually trigger completion
        ['<C-;>'] = cmp.mapping.complete(),
      },
    })
  end,
}
