-- Fleet trust only, because the plugin records keystrokes typed in Markdown. A
-- nonfleet box is someone else's machine, so it gets no spec and lazy never
-- clones the plugin there.
--
-- A normal remote spec rather than a `dir =` local checkout: a `dir` that is not
-- on disk errors on every startup no matter what `cond` says.
--
-- The plugin ships no directories of its own; these are the fleet's, and naming
-- them is this file's whole job. Capture runs while the buffer is under one of
-- them, so a machine that has not run `syncer apply` has neither and captures
-- nothing.
--
-- data_dir is absent because TYPOS_DATA_DIR, exported in .zshrc, names the
-- directory for both the plugin and the `typos` CLI.
--
-- nvim loads the lazy clone, not ~/code/typos, so a local Lua change needs a
-- push and `:Lazy update` to show up here.
return {
  'datapointchris/typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposOn', 'TyposOff', 'TyposAuto', 'TyposStatus' },
  opts = {
    watch_dirs = { '~/notes', '~/shart' },
  },
}
