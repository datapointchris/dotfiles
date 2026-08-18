-- Floats ui2's cmdline window in the centre of the editor while you type, and
-- puts it back on CmdlineLeave so the message the command produces still lands
-- at the bottom. ui2 reasserts the bottom position on every message it renders,
-- which is why the float has to be per-cmdline rather than permanent.
--
-- Border and cmdheight come from core/options.lua: winborder is inherited when
-- border is left unset, and cmdheight must be 0 or ui2 keeps the window shown.
return {
  'rachartier/tiny-cmdline.nvim',
  event = 'VeryLazy',
  opts = function()
    return {
      -- blink.cmp positions its own menu, so it needs telling where the window
      -- went; everything else follows vim.g.ui_cmdline_pos on its own.
      on_reposition = require('tiny-cmdline').adapters.blink,
    }
  end,
}
