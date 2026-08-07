local checkout = vim.fn.expand('~/code/typos')

-- Role, not platform: this reads ~/notes and ~/shart, which are Syncthing
-- personal directories that do not exist on the work box. It was gated on
-- PLATFORM ~= 'wsl' only because the work box happens to be the WSL one.
--
-- Contributed as no spec at all rather than `cond = false`: cond gates loading,
-- while lazy still resolves the spec, so a `dir` that is not on disk is an
-- error on every startup no matter what cond says. The checkout test carries
-- the same fix to any machine that has not cloned it yet.
if vim.env.MACHINE_ROLE == 'work' or vim.fn.isdirectory(checkout) == 0 then return {} end

return {
  dir = checkout,
  name = 'typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposToggle', 'TyposStatus' },
  opts = {
    notes_root = vim.fn.expand('~/notes'),
    data_dir = vim.fn.expand('~/shart/typing'),
  },
}
