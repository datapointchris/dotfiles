return {
  {
    'projekt0n/github-nvim-theme',
    name = 'github-theme',
    lazy = false, -- make sure we load this during startup if it is your main colorscheme
    priority = 1000, -- make sure to load this before all the other start plugins
    cond = not vim.g.vscode, -- VSCode handles themes natively
    config = function()
      require('github-theme').setup()
      vim.cmd('colorscheme github_dark_dimmed')
    end,
  },
  {
    'rose-pine/neovim',
    lazy = false,
    priority = 1000,
    config = function()
      require('rose-pine').setup({
        variant = 'auto', -- auto, main, moon, or dawn
        dark_variant = 'main', -- main, moon, or dawn
      })
    end,
  },
  { 'rebelot/kanagawa.nvim', lazy = false },
  { 'ellisonleao/gruvbox.nvim', lazy = false, event = 'VeryLazy' },
  { 'sainnhe/gruvbox-material', lazy = false, event = 'VeryLazy', version = '*' },
  { 'AlexvZyl/nordic.nvim', lazy = false, priority = 1000 },
  { 'navarasu/onedark.nvim', event = 'VeryLazy' },
  { 'EdenEast/nightfox.nvim' },
  { 'craftzdog/solarized-osaka.nvim' },
  { 'mhartington/oceanic-next' },
  { 'datapointchris/flexoki-moon-nvim' },
}
