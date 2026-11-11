-- A normal remote spec rather than a `dir =` local checkout, so lazy resolves it
-- like every other plugin and there is nothing here to guard on. The gate this
-- replaces was three conditions deep — PLATFORM, then MACHINE_ROLE, then testing
-- for the checkout and ~/notes — because a `dir` that is not on disk errors on
-- every startup no matter what `cond` says, which no label could fix.
--
-- The plugin ships no directories of its own; these are the fleet's, and naming
-- them is this file's whole job. Capture runs while the buffer is under one of
-- them, so a machine that has not run `syncer apply` has neither and captures
-- nothing — no condition has to express that.
--
-- data_dir is deliberately absent: TYPOS_DATA_DIR in .zshrc points both this and
-- the `typos` CLI at the synced location, so the path is declared once.
--
-- Consequence worth knowing: nvim loads the lazy clone, not ~/code/typos, so a
-- local Lua change needs a push and `:Lazy update` to show up here.
return {
  'datapointchris/typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposOn', 'TyposOff', 'TyposAuto', 'TyposStatus' },
  opts = {
    watch_dirs = { '~/notes', '~/shart' },
  },
}
