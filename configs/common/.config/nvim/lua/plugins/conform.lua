-- conform.nvim - Modern formatter plugin
-- https://github.com/stevearc/conform.nvim
return {
  'stevearc/conform.nvim',
  event = { 'BufReadPre', 'BufNewFile' },
  config = function()
    local conform = require('conform')

    -- Register .keymap filetype
    vim.filetype.add({
      extension = {
        keymap = 'dts', -- devicetree syntax works well for ZMK keymaps
      },
    })

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
        dts = { 'keymap_align' },
      },
      formatters = {
        shfmt = {
          prepend_args = { '-i', '2' },
        },
        keymap_align = {
          command = 'keymap-align',
          args = { '-k', '$FILENAME' },
          stdin = false,
        },
      },
      format_on_save = {
        timeout_ms = 1000,
        lsp_format = 'fallback',
      },
    })
  end,
}
