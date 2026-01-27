return {
  'nvim-treesitter/nvim-treesitter',
  branch = 'main',
  build = ':TSUpdate',
  lazy = false,
  event = { 'BufReadPre', 'BufNewFile' },
  dependencies = {
    'nvim-treesitter/nvim-treesitter-textobjects',
    'MeanderingProgrammer/treesitter-modules.nvim',
  },
  config = function()
    require('nvim-treesitter-textobjects').setup({
      branch = 'main',
    })
    require('treesitter-modules').setup({
      auto_install = true,
      sync_install = false,
      highlight = { enable = true },
      indent = { enable = true },
      ensure_installed = {
        -- Web development (Vue needs all of these for proper injection)
        'vue',
        'typescript',
        'tsx',
        'javascript',
        'html',
        'css',
        'scss',
        -- Data formats
        'json',
        'yaml',
        'toml',
        -- Backend
        'go',
        'gomod',
        'gosum',
        'sql',
        'python',
        'rust',
        -- Systems programming (ZMK, embedded)
        'c',
        'cpp',
        -- Shell/scripting
        'bash',
        'lua',
        'fish',
        'nu',
        'nix',
        -- Infrastructure
        'terraform',
        'hcl',
        'proto',
        -- Build systems
        'cmake',
        'make',
        -- Docs
        'markdown',
        'markdown_inline',
        -- Config
        'dockerfile',
        'gitignore',
        'vim',
        'vimdoc',
      },
      ignore_install = {},
      modules = {},
      incremental_selection = {
        enable = true,
        keymaps = {
          init_selection = '<leader>gnn',
          node_incremental = '<leader>grn',
          scope_incremental = '<leader>grc',
          node_decremental = '<leader>grm',
        },
      },
    })
  end,
}
