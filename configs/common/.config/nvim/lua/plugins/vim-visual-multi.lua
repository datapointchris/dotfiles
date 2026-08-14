return {
  'mg979/vim-visual-multi',
  lazy = false,
  init = function()
    -- Empty disables the map. Vertical cursors are native — <C-v> then I / A /
    -- $A — and both chords one would want are taken: <C-Up>/<C-Down> by
    -- vim-tmux-navigator, <C-S-Up>/<C-S-Down> by winresize. Omitting these
    -- entries instead lets VM claim <C-Up>/<C-Down> back. <C-n> and \\A stand.
    vim.g.VM_maps = {
      ['Add Cursor Up'] = '',
      ['Add Cursor Down'] = '',
    }
  end,
}
