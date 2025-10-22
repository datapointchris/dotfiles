-- lazydev.nvim is a plugin that properly configures lua_ls for editing your Neovim config by lazily updating your workspace libraries.
return {
  {
    'folke/lazydev.nvim',
    ft = 'lua', -- only load on lua files
    cond = not vim.g.vscode, -- VSCode has Lua language server support
    opts = {
      library = {
        -- See the configuration section for more details
        -- Load luvit types when the `vim.uv` word is found
        { path = 'luvit-meta/library', words = { 'vim%.uv' } },
      },
    },
  },
  { 'Bilal2453/luvit-meta', lazy = true }, -- optional `vim.uv` typings
  -- TESTING this out, it is defined in the nvim-cmp instead
  -- { -- optional completion source for require statements and module annotations
  --   'hrsh7th/nvim-cmp',
  --   opts = function(_, opts)
  --     opts.sources = opts.sources or {}
  --     table.insert(opts.sources, {
  --       name = 'lazydev',
  --       group_index = 0, -- set group index to 0 to skip loading LuaLS completions
  --     })
  --   end,
  -- },
}
