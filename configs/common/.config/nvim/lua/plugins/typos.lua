return {
  dir = '~/code/typos',
  name = 'typos',
  ft = 'markdown', -- Notes are .md, no need to load otherwise
  cmd = { 'TyposToggle', 'TyposStatus' },
  opts = {
    notes_root = vim.fn.expand('~/notes'),
    data_dir = vim.fn.expand('~/shart/typing'),
  },
}
