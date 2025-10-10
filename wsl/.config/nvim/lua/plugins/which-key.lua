return {
  'folke/which-key.nvim',
  event = 'VeryLazy',
  cond = not vim.g.vscode, -- VSCode doesn't need keymap popup hints
  opts = {},
  config = function()
    local wk = require('which-key')
    wk.add({
      mode = { 'n' },
      { '<leader>cc', group = ' Copilot Chat', icon = ' ' },
      { '<leader>cca', icon = ' ' },
      { '<leader>ccd', icon = ' ' },
      { '<leader>cch', icon = ' ' },
      { '<leader>ccp', icon = ' ' },
      { '<leader>ccP', icon = ' ' },
      { '<leader>ccs', icon = ' ' },
      { '<leader>cct', icon = ' ' },
      { '<leader>ccb', group = ' Buffer', icon = ' ' },
      { '<leader>ccba', icon = ' ' },
      { '<leader>ccbd', icon = ' ' },
      { '<leader>ccbe', icon = ' ' },
      { '<leader>ccbr', icon = ' ' },
      { '<leader>ccbt', icon = ' ' },
      { '<leader>ccc', group = ' Clipboard', icon = ' ' },
      { '<leader>ccca', icon = ' ' },
      { '<leader>cccd', icon = ' ' },
      { '<leader>ccce', icon = ' ' },
      { '<leader>cccr', icon = ' ' },
      { '<leader>ccct', icon = ' ' },
      { '<leader>ccg', group = ' Git', icon = ' ' },
      { '<leader>ccgm', icon = ' ' },
      { '<leader>h', group = ' Help & Workflows', icon = ' ' },
      { '<leader>hw', icon = ' ' },
      { '<leader>hk', icon = ' ' },
      { '<leader>hh', icon = ' ' },
      { '<leader>o', group = ' Obsidian', icon = ' ' },
      { '<leader>q', group = ' Quitting' },
    })
    wk.add({
      mode = { 'x' },
      { '<leader>cc', group = ' Copilot Chat', icon = ' ' },
      { '<leader>ccv', group = ' Visual', icon = ' ' },
      { '<leader>ccva', icon = ' ' },
      { '<leader>ccvd', icon = ' ' },
      { '<leader>ccve', icon = ' ' },
      { '<leader>ccvr', icon = ' ' },
      { '<leader>ccvt', icon = ' ' },
    })
    wk.setup({})
  end,
  keys = {
    {
      '<leader>?',
      function()
        require('which-key').show({
          global = false,
        })
      end,
      desc = 'Buffer Local Keymaps (which-key)',
    },
  },
}
