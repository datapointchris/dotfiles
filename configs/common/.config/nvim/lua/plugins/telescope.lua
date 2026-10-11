return { -- Fuzzy Finder (files, lsp, etc)
  'nvim-telescope/telescope.nvim',
  event = 'VimEnter',
  dependencies = {
    'nvim-lua/plenary.nvim',
    'echasnovski/mini.nvim', -- icons via mini.icons mock
    'nvim-telescope/telescope-ui-select.nvim',
    { 'nvim-telescope/telescope-fzf-native.nvim', build = 'make' },
  },
  config = function()
    require('telescope').setup({
      defaults = {
        file_ignore_patterns = { '.git/', '.gitsecret', '**/tmux/plugins/**' },
      },
      pickers = {
        colorscheme = { enable_preview = true },
        find_files = { hidden = true },
        live_grep = {
          additional_args = function()
            return { '--hidden' }
          end,
        },
      },
      extensions = {
        fzf = {},
        ['ui-select'] = { require('telescope.themes').get_dropdown() },
      },
    })

    require('telescope').load_extension('fzf')
    require('telescope').load_extension('ui-select')
  end,
}
