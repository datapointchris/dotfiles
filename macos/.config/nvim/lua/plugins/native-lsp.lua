-- Native LSP Setup for Neovim 0.11+ with Mason Tool Management
-- Mason is used purely for tool installation, native LSP handles configuration
return {
  -- Mason for tool installation (not configuration)
  {
    'williamboman/mason.nvim',
    cmd = 'Mason',
    build = ':MasonUpdate',
    config = function()
      require('mason').setup({
        ui = {
          border = 'rounded',
          icons = {
            package_installed = '✓',
            package_pending = '➜',
            package_uninstalled = '✗',
          },
        },
      })
    end,
  },

  -- Auto-install LSP servers based on configured servers
  {
    'WhoIsSethDaniel/mason-tool-installer.nvim',
    dependencies = { 'williamboman/mason.nvim' },
    config = function()
      -- Map your configured servers to Mason package names
      local server_to_mason = {
        bashls = 'bash-language-server',
        basedpyright = 'basedpyright',
        cssls = 'css-lsp',
        docker_compose_language_service = 'docker-compose-language-service',
        dockerls = 'dockerfile-language-server',
        eslint = 'eslint-lsp',
        gopls = 'gopls',
        html = 'html-lsp',
        jsonls = 'json-lsp',
        lua_ls = 'lua-language-server',
        marksman = 'marksman',
        ruff = 'ruff',
        rust_analyzer = 'rust-analyzer',
        sqlls = 'sqlls',
        taplo = 'taplo',
        terraformls = 'terraform-ls',
        tflint = 'tflint',
        ts_ls = 'typescript-language-server',
        vimls = 'vim-language-server',
        yamlls = 'yaml-language-server',
      }

      -- Get tools to install from your server list
      local servers = require('lsp').get_servers()
      local tools_to_install = {}

      for _, server in ipairs(servers) do
        local mason_name = server_to_mason[server]
        if mason_name then
          table.insert(tools_to_install, mason_name)
        else
          vim.notify('No Mason package found for ' .. server, vim.log.levels.WARN)
        end
      end

      require('mason-tool-installer').setup({
        ensure_installed = tools_to_install,
        auto_update = true, -- Set to true if you want automatic updates
        run_on_start = true,
        start_delay = 3000, -- 3 second delay to avoid startup lag
      })

      -- Add health check command
      vim.api.nvim_create_user_command('LspToolsHealth', function()
        print('\n=== LSP Tools Health Check ===')
        print('Configured servers: ' .. #servers)
        print('Mason packages to install: ' .. #tools_to_install)
        print('\nServer -> Mason Package Mapping:')
        for _, server in ipairs(servers) do
          local mason_name = server_to_mason[server]
          if mason_name then
            print('  ✓ ' .. server .. ' -> ' .. mason_name)
          else
            print('  ✗ ' .. server .. ' -> NO MASON PACKAGE')
          end
        end
        print('\nUse :Mason to manually manage tools')
      end, { desc = 'Check LSP tools installation status' })
    end,
  },

  -- Disable conflicting plugins that are replaced by native LSP
  {
    'williamboman/mason-lspconfig.nvim',
    enabled = false,
  },
  {
    'neovim/nvim-lspconfig',
    enabled = false,
  },
  {
    'nvimtools/none-ls.nvim',
    enabled = false,
  },

  -- Keep only essential dependencies
  {
    'L3MON4D3/LuaSnip',
    version = 'v2.*',
    build = 'make install_jsregexp',
    event = 'InsertEnter',
    config = function()
      local luasnip = require('luasnip')

      -- Load snippets from friendly-snippets
      require('luasnip.loaders.from_vscode').lazy_load()

      -- Custom snippet configuration
      luasnip.config.set_config({
        history = true,
        updateevents = 'TextChanged,TextChangedI',
        enable_autosnippets = true,
      })

      -- Keymaps for snippet navigation
      vim.keymap.set({ 'i', 's' }, '<C-k>', function()
        if luasnip.expand_or_jumpable() then luasnip.expand_or_jump() end
      end, { desc = 'Expand or jump in snippet' })

      vim.keymap.set({ 'i', 's' }, '<C-j>', function()
        if luasnip.jumpable(-1) then luasnip.jump(-1) end
      end, { desc = 'Jump back in snippet' })
    end,
  },
  {
    'rafamadriz/friendly-snippets',
    event = 'InsertEnter',
  },

  -- Native LSP configuration
  {
    name = 'native-lsp',
    dir = vim.fn.stdpath('config') .. '/lsp',
    lazy = false,
    priority = 1000,
    config = function()
      -- Set up additional LSP keymaps (defaults are: gra, gri, grn, grr, grt, gO, K, <C-S>)
      local function set_lsp_keymaps()
        -- NOTE: Neovim 0.11+ provides these DEFAULT keymaps automatically:
        -- gra → vim.lsp.buf.code_action() (Normal & Visual)
        -- gri → vim.lsp.buf.implementation()
        -- grn → vim.lsp.buf.rename()
        -- grr → vim.lsp.buf.references()
        -- grt → vim.lsp.buf.type_definition()
        -- gO  → vim.lsp.buf.document_symbol()
        -- K   → vim.lsp.buf.hover() (unless keywordprg is set)
        -- <C-S> (insert) → vim.lsp.buf.signature_help()

        -- Additional non-conflicting keymaps
        vim.keymap.set('n', '<leader>f', function() vim.lsp.buf.format({ async = true }) end, { desc = 'LSP: Format' })

        vim.keymap.set('n', '<leader>ws', vim.lsp.buf.workspace_symbol, { desc = 'LSP: Workspace Symbol' })
        vim.keymap.set('n', '<leader>e', vim.diagnostic.open_float, { desc = 'Show Diagnostic' })
        vim.keymap.set('n', '[d', vim.diagnostic.goto_prev, { desc = 'Previous Diagnostic' })
        vim.keymap.set('n', ']d', vim.diagnostic.goto_next, { desc = 'Next Diagnostic' })
        vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Diagnostic Location List' })

        -- Additional signature help binding (native <C-S> also available)
        vim.keymap.set('i', '<C-h>', vim.lsp.buf.signature_help, { desc = 'LSP: Signature Help' })
      end

      -- Configure diagnostics
      vim.diagnostic.config({
        virtual_text = {
          spacing = 2,
          prefix = '●',
        },
        signs = true,
        underline = true,
        update_in_insert = false,
        severity_sort = true,
        float = {
          border = 'rounded',
          source = 'always',
          header = '',
          prefix = '',
        },
      })

      -- Set diagnostic signs
      local signs = {
        Error = '✘',
        Warn = '▲',
        Hint = '⚑',
        Info = '»',
      }
      for type, icon in pairs(signs) do
        local hl = 'DiagnosticSign' .. type
        vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = hl })
      end

      -- Set up keymaps
      set_lsp_keymaps()

      -- Load and setup native LSP configuration
      require('lsp').setup()
    end,
  },
}
