return {
  'mg979/vim-visual-multi',
  lazy = false,
  init = function()
    -- Move Add Cursor Up/Down off <C-Up>/<C-Down> so those chords reach
    -- vim-tmux-navigator for pane navigation.
    vim.g.VM_maps = {
      ['Add Cursor Up'] = '<C-S-Up>',
      ['Add Cursor Down'] = '<C-S-Down>',
    }
  end,
}
