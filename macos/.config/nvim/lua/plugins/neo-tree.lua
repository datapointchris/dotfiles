return {
  'nvim-neo-tree/neo-tree.nvim',
  version = '*',
  cond = not vim.g.vscode, -- VSCode has native file explorer
  dependencies = {
    'nvim-lua/plenary.nvim',
    'nvim-tree/nvim-web-devicons', -- not strictly required, but recommended
    'MunifTanjim/nui.nvim',
  },
  cmd = 'Neotree',
  keys = { {
    '\\',
    ':Neotree reveal<CR>',
    desc = 'NeoTree reveal',
    silent = true,
  } },
  opts = {
    filesystem = {
      filtered_items = {
        visible = true,
        show_hidden_count = true,
        hide_dotfiles = false,
        hide_gitignored = true,
        hide_by_name = { '.git', '.DS_Store', 'thumbs.db' },
        never_show = {},
      },
    },
  },
}
