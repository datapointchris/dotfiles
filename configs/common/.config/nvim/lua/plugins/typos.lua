return {
  dir = '~/code/typos',
  name = 'typos',
  -- Role, not platform: this reads ~/notes and ~/shart, which are Syncthing
  -- personal directories that do not exist on the work box. It was gated on
  -- PLATFORM ~= 'wsl' only because the work box happens to be the WSL one.
  cond = vim.env.MACHINE_ROLE ~= 'work',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposToggle', 'TyposStatus' },
  opts = {
    notes_root = vim.fn.expand('~/notes'),
    data_dir = vim.fn.expand('~/shart/typing'),
  },
}
