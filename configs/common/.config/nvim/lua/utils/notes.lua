local M = {}

function M.search_notes(search_term)
  require('telescope.builtin').find_files({
    search_file = search_term,
    hidden = false,
    search_dirs = '~/Documents/notes/',
  })
end

vim.api.nvim_create_user_command('SearchNotes', M.search_notes, { desc = 'Search Notes' })

return M
