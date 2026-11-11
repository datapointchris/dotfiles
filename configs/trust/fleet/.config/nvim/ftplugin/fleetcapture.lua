-- The note's comments are # lines, as a git commit message's are, so gc uncomments
-- one of the options the note opens on.
vim.bo.commentstring = '# %s'
vim.opt_local.wrap = true
vim.opt_local.linebreak = true

-- A capture is prose typed in one go. blink.cmp checks this before its own enabled
-- function, so no completion menu is built on each keypress.
vim.b.completion = false

-- The capture is written on the first empty line, under the options. This runs
-- before a +startinsert argument, so insert mode starts there.
for row, line in ipairs(vim.api.nvim_buf_get_lines(0, 0, -1, false)) do
  if line == '' then
    vim.api.nvim_win_set_cursor(0, { row, 0 })
    break
  end
end
