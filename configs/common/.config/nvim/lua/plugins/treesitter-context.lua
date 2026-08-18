return {
  'nvim-treesitter/nvim-treesitter-context',
  event = { 'BufReadPost', 'BufNewFile' },
  opts = {
    max_lines = 3,
    -- Trim the innermost scopes so the enclosing class survives deep nesting
    trim_scope = 'inner',
    -- Below this the context costs more rows than the split can spare
    min_window_height = 20,
  },
}
