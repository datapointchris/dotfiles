return { -- Collection of various small independent plugins/modules
  'echasnovski/mini.nvim',
  config = function()
    -- Icon provider for the whole config. The mock makes plugins that request
    -- nvim-web-devicons (bufferline, lualine, telescope, trouble, yazi, …)
    -- transparently use mini.icons, so nvim-web-devicons is no longer needed.
    require('mini.icons').setup()
    MiniIcons.mock_nvim_web_devicons()

    -- Auto-close/pair brackets and quotes (replaces nvim-autopairs).
    require('mini.pairs').setup()

    -- Better Around/Inside textobjects
    require('mini.ai').setup({
      n_lines = 500,
      custom_textobjects = {
        ['_'] = { '%f[^_]()[^_]+()%f[_]' },
      },
    })
    --  - va)  - [V]isually select [A]round [)]paren
    --  - yinq - [Y]ank [I]nside [N]ext [Q]uote
    --  - ci'  - [C]hange [I]nside [']quote

    -- Add/delete/replace surroundings (brackets, quotes, etc.)
    require('mini.surround').setup()
    -- - saiw) - [S]urround [A]dd [I]nner [W]ord [)]Paren
    -- - sd'   - [S]urround [D]elete [']quotes
    -- - sr)'  - [S]urround [R]eplace [)] [']

    -- Commenting (gc/gcc) is provided natively by Neovim 0.10+, so mini.comment
    -- is no longer needed.

    -- Delete a buffer without closing its window/tab layout (unlike :bdelete).
    -- Keymap: <leader>bd in core/keymaps.lua.
    require('mini.bufremove').setup()
  end,
}
