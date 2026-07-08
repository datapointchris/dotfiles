return {
  'akinsho/bufferline.nvim',
  version = '*',
  dependencies = 'nvim-tree/nvim-web-devicons',
  config = function()
    require('bufferline').setup({
      options = {
        -- Render one entry per tab page (matches the <tab>/<s-tab> workflow),
        -- not one per open buffer.
        mode = 'tabs',
        -- Show a differentiating parent directory only when two tabs share a
        -- filename, instead of abbreviating every path like the native tabline.
        show_duplicate_prefix = true,
        diagnostics = 'nvim_lsp',
        separator_style = 'slope',
        show_buffer_close_icons = false,
        show_close_icon = false,
        always_show_bufferline = true,
        indicator = { style = 'underline' },
      },
    })
  end,
}
