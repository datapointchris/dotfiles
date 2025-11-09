return {
  {
    'stevearc/oil.nvim',
    cond = not vim.g.vscode, -- VSCode has native file navigation
    dependencies = { 'nvim-tree/nvim-web-devicons' },
    config = function()
      require('oil').setup({
        default_file_explorer = true,
        delete_to_trash = true,
        skip_confirm_for_simple_edits = true,
        columns = { 'icon' },
        -- keymaps = {
        --   ['<C-h>'] = false,
        --   ['<C-l>'] = false,
        --   ['<C-k>'] = false,
        --   ['<C-j>'] = false,
        --   ['<M-h>'] = 'actions.select_split',
        -- },
        win_options = {},
        view_options = {
          show_hidden = true,
          natural_order = true,
          is_always_hidden = function(name, bufnr) return name == '..' or name == '.git' end,
        },
        float = {
          padding = 5,
        },
      })
    end,
  },
}
