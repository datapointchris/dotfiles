return {
  'stevearc/dressing.nvim',
  event = 'VeryLazy',
  -- telescope-ui-select owns vim.ui.select (fuzzy, consistent with the rest of
  -- the telescope-centric config). dressing handles vim.ui.input only, or the
  -- two race to override vim.ui.select.
  opts = {
    input = { enabled = true },
    select = { enabled = false },
  },
}
