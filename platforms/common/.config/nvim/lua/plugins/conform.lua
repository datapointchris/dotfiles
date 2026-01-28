-- conform.nvim - Modern formatter plugin
-- https://github.com/stevearc/conform.nvim
return {
  'stevearc/conform.nvim',
  event = { 'BufReadPre', 'BufNewFile' },
  config = function()
    local conform = require('conform')

    conform.setup({
      formatters_by_ft = {
        lua = { 'stylua' },
        python = { 'ruff_format' },
        javascript = { 'prettier' },
        typescript = { 'prettier' },
        javascriptreact = { 'prettier' },
        typescriptreact = { 'prettier' },
        json = { 'prettier' },
        yaml = { 'prettier' },
        markdown = { 'markdownlint' },
        css = { 'prettier' },
        html = { 'prettier' },
        sh = { 'shfmt' },
        bash = { 'shfmt' },
        go = { 'gofumpt' },
        rust = { 'rustfmt' },
        terraform = { 'terraform_fmt' },
      },
      formatters = {
        shfmt = {
          prepend_args = { '-i', '2' },
        },
      },
      format_on_save = {
        timeout_ms = 1000,
        lsp_format = 'fallback',
      },
    })
  end,
}
