return { -- Collection of various small independent plugins/modules
  'echasnovski/mini.nvim',
  config = function()
    -- require("mini.icons").setup()

    -- Better Around/Inside textobjects
    require('mini.ai').setup({ n_lines = 500 })
    --  - va)  - [V]isually select [A]round [)]paren
    --  - yinq - [Y]ank [I]nside [N]ext [Q]uote
    --  - ci'  - [C]hange [I]nside [']quote

    -- Add/delete/replace surroundings (brackets, quotes, etc.)
    require('mini.surround').setup()
    -- - saiw) - [S]urround [A]dd [I]nner [W]ord [)]Paren
    -- - sd'   - [S]urround [D]elete [']quotes
    -- - sr)'  - [S]urround [R]eplace [)] [']

    -- Commenting/uncommenting lines and blocks of code
    require('mini.comment').setup()
    -- - gc   - Toggle comment (like `gcip` - comment inner paragraph) for both Normal and Visual modes
    -- - gcc  - [G]CC [C]omment [C]urrent line
    -- - gc2j - [G]CC [C]omment [2] lines [J] below
  end,
}
