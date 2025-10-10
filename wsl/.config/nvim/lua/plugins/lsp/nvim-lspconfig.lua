return {
  'neovim/nvim-lspconfig',
  cond = not vim.g.vscode, -- VSCode has built-in LSP and IntelliSense
  dependencies = {
    'williamboman/mason.nvim',
    'williamboman/mason-lspconfig.nvim',
    'WhoIsSethDaniel/mason-tool-installer.nvim',
    'hrsh7th/cmp-nvim-lsp',
    {
      'antosha417/nvim-lsp-file-operations',
      dependencies = {
        'nvim-lua/plenary.nvim',
        'nvim-neo-tree/neo-tree.nvim',
      },
      config = function() require('lsp-file-operations').setup() end,
    },
  },
  config = function()
    local capabilities = vim.lsp.protocol.make_client_capabilities()
    capabilities = vim.tbl_deep_extend('force', capabilities, require('cmp_nvim_lsp').default_capabilities())

    -- See `:help lspconfig-all` for a list of all the pre-configured LSPs
    local servers = {
      bashls = {},
      basedpyright = { disableOrganizeImports = true },
      css_variables = {},
      cssls = {},
      docker_compose_language_service = {},
      dockerls = {},
      eslint = {},
      gopls = {},
      html = {},
      htmx = {},
      jinja_lsp = {},
      jsonls = {},
      marksman = {},
      nginx_language_server = {},
      ruff = { trace = 'messages', init_options = {
        settings = {
          logLevel = 'debug',
        },
      } },
      rust_analyzer = {},
      sqlls = {},
      taplo = {}, -- TOML
      terraformls = {},
      tflint = {},
      ts_ls = {},
      vimls = {},
      lua_ls = {
        settings = {
          Lua = {
            completion = {
              callSnippet = 'Replace',
            },
          },
        },
      },
    }

    require('mason').setup()

    local ensure_installed = vim.tbl_keys(servers or {})
    vim.list_extend(ensure_installed, { 'stylua' })
    require('mason-tool-installer').setup({ ensure_installed = ensure_installed })

    require('mason-lspconfig').setup({
      handlers = {
        function(server_name)
          local server = servers[server_name] or {}
          -- This handles overriding only values explicitly passed
          -- by the server configuration above. Useful when disabling
          -- certain features of an LSP (for example, turning off formatting for ts_ls)
          server.capabilities = vim.tbl_deep_extend('force', {}, capabilities, server.capabilities or {})

          -- Custom setup for htmx to exclude markdown
          if server_name == 'htmx' then
            server.filetypes = vim.tbl_filter(function(ft) return ft ~= 'markdown' end, server.filetypes or {})
          end

          require('lspconfig')[server_name].setup(server)
        end,
      },
    })

    vim.api.nvim_create_autocmd('LspAttach', {
      group = vim.api.nvim_create_augroup('LspConfig', {
        clear = true,
      }),
      callback = function(event)
        -- Highlight references on hover
        local client = vim.lsp.get_client_by_id(event.data.client_id)
        if client and client.supports_method(vim.lsp.protocol.Methods.textDocument_documentHighlight) then
          local highlight_augroup = vim.api.nvim_create_augroup('LspHighlight', {
            clear = false,
          })
          vim.api.nvim_create_autocmd({ 'CursorHold', 'CursorHoldI' }, {
            buffer = event.buf,
            group = highlight_augroup,
            callback = vim.lsp.buf.document_highlight,
          })

          vim.api.nvim_create_autocmd({ 'CursorMoved', 'CursorMovedI' }, {
            buffer = event.buf,
            group = highlight_augroup,
            callback = vim.lsp.buf.clear_references,
          })

          vim.api.nvim_create_autocmd('LspDetach', {
            group = vim.api.nvim_create_augroup('LspDetachConfig', {
              clear = true,
            }),
            callback = function(event2)
              vim.lsp.buf.clear_references()
              vim.api.nvim_clear_autocmds({
                group = 'LspHighlight',
                buffer = event2.buf,
              })
            end,
          })
        end
      end,
    })
  end,
}
