return {
  'nvimtools/none-ls.nvim',
  cond = not vim.g.vscode, -- VSCode handles linting and formatting
  dependencies = {
    'williamboman/mason.nvim',
    'jay-babu/mason-null-ls.nvim',
  },
  lazy = true,
  event = { 'BufReadPre', 'BufNewFile' },
  config = function()
    local null_ls = require('null-ls')
    local formatting = null_ls.builtins.formatting
    local diagnostics = null_ls.builtins.diagnostics

    local sources = {
      diagnostics.actionlint,
      diagnostics.ansiblelint,
      diagnostics.codespell,
      diagnostics.dotenv_linter,
      diagnostics.hadolint, -- dockerfile linter
      diagnostics.markdownlint.with({ extra_args = { '--ignore', '*copilot-chat*' } }),
      diagnostics.mypy,
      diagnostics.sqlfluff.with({ extra_args = { '--dialect', 'postgres' } }),
      diagnostics.terraform_validate,
      diagnostics.zsh,
      formatting.markdownlint,
      formatting.mdformat,
      formatting.nginx_beautifier,
      formatting.pg_format,
      formatting.prettier.with({
        filetypes = {
          'javascript',
          'javascriptreact',
          'typescript',
          'typescriptreact',
          'markdown',
          'json',
          'yaml',
          'html',
          'css',
          'scss',
          'less',
          'vue',
          'svelte',
          'graphql',
          'jsonc',
        },
      }),
      formatting.prettierd.with({
        filetypes = {
          'javascript',
          'javascriptreact',
          'typescript',
          'typescriptreact',
          'markdown',
          'json',
          'yaml',
          'html',
          'css',
          'scss',
          'less',
          'vue',
          'svelte',
          'graphql',
          'jsonc',
        },
      }),
      formatting.shfmt.with({
        filetypes = { 'bash', 'zsh' },
        extra_args = { '-i', '4' },
      }),

      formatting.sqlfluff,
      formatting.terraform_fmt,
    }

    require('mason').setup()

    null_ls.setup({ sources = sources })

    require('mason-null-ls').setup({
      ensure_installed = {},
      automatic_installation = true,
    })
  end,
}
