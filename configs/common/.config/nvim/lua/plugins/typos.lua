-- A normal remote spec rather than a `dir =` local checkout, so lazy resolves it
-- like every other plugin and there is nothing here to guard on. The gate this
-- replaces was three conditions deep — PLATFORM, then MACHINE_ROLE, then testing
-- for the checkout and ~/notes — because a `dir` that is not on disk errors on
-- every startup no matter what `cond` says, which no label could fix.
--
-- Nothing conditional is needed now: capture is scoped to notes_root, so on a
-- machine without ~/notes the on_key hook matches no buffer and writes nothing,
-- and setup() creates no directories. A no-op by construction.
--
-- Consequence worth knowing: nvim loads the lazy clone, not ~/code/typos, so a
-- local Lua change needs a push and `:Lazy update` to show up here.
return {
  'datapointchris/typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposToggle', 'TyposStatus' },
  opts = {
    notes_root = vim.fn.expand('~/notes'),
    data_dir = vim.fn.expand('~/shart/typing'),
  },
}
