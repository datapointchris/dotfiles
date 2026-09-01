-- Cinnamon animates a scroll by stepping the cursor's buffer line and the
-- window's screen row as if the two advanced together. A diff window is the one
-- place they do not: a closed fold compresses many buffer lines into one screen
-- row, and the filler rows opposite a hunk expand one buffer line into several.
--
-- Both halves are measurable in a plain `nvim -d`. Its `get_line_error` walks the
-- gap fold by fold and counts a closed fold as one line, while `move_cursor`
-- adds that total straight onto the cursor's line number, so a <C-d> spanning 30
-- buffer lines resolves to a distance of 19. And stepping one line at a time
-- through a folded region leaves the screen row unmoved for eleven consecutive
-- steps, after which it leaps.
--
-- The animation therefore walks the cursor to lines that are not where it thinks
-- they are, and drags the view after it. Diffview makes this constant by setting
-- `foldlevel = 0` and `foldenable` on every diff window. Ordinary files escape it
-- because `foldlevelstart` is 99 here, so nothing starts closed.
--
-- Skipping the animation leaves the motion itself untouched: cinnamon runs the
-- command before it decides whether to animate, so a suppressed <C-d> lands
-- exactly where the native one would.
local function suppress_in_diff_windows()
  local cinnamon = require('cinnamon')
  local scroll = cinnamon.scroll

  -- Every keymap cinnamon binds resolves `scroll` on the module table when the
  -- key is pressed, so replacing it here covers all of them without restating
  -- the list. Diff mode is a property of the window rather than the buffer, and
  -- `:diffthis` sets it without firing OptionSet, so the only reliable moment to
  -- read it is the keypress itself.
  cinnamon.scroll = function(command, options)
    vim.b.cinnamon_disable = vim.wo.diff
    return scroll(command, options)
  end
end

return {
  'declancm/cinnamon.nvim',
  version = '*', -- use latest release
  opts = {
    keymaps = {
      basic = true,
      extra = true,
    },
  },
  config = function(_, opts)
    require('cinnamon').setup(opts)
    suppress_in_diff_windows()
  end,
}
