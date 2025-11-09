return {
  'leath-dub/snipe.nvim',
  cond = not vim.g.vscode, -- VSCode has native buffer/tab switching
  keys = {
    { 'gb', function() require('snipe').open_buffer_menu() end, desc = 'Open Snipe buffer menu' },
  },
  opts = {},
}
