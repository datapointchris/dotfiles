-- A normal remote spec rather than a `dir =` local checkout, so lazy resolves it
-- like every other plugin and there is nothing here to guard on. The gate this
-- replaces was three conditions deep — PLATFORM, then MACHINE_ROLE, then testing
-- for the checkout and ~/notes — because a `dir` that is not on disk errors on
-- every startup no matter what `cond` says, which no label could fix.
--
-- `dirs` is the auto-on list: capture runs while the buffer is under one of them.
-- A machine that has not run `syncer apply` has neither, so it captures nothing
-- without any condition expressing that.
--
-- Consequence worth knowing: nvim loads the lazy clone, not ~/code/typos, so a
-- local Lua change needs a push and `:Lazy update` to show up here.
return {
  'datapointchris/typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposOn', 'TyposOff', 'TyposAuto', 'TyposStatus' },
  opts = {
    dirs = { '~/notes' },
    data_dir = '~/shart/typing',
  },
}
