return { -- Fuzzy Finder (files, lsp, etc)
  'nvim-telescope/telescope.nvim',
  event = 'VimEnter',
  branch = '0.1.x',
  cond = not vim.g.vscode, -- VSCode has native fuzzy finding
  dependencies = {
    'nvim-lua/plenary.nvim',
    'nvim-tree/nvim-web-devicons',
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
