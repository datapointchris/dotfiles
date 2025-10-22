-- Python Ruff Language Server
return {
  cmd = { 'ruff', 'server', '--preview' },
  filetypes = { 'python' },
  root_markers = {
    'pyproject.toml',
    'ruff.toml',
    '.ruff.toml',
    'setup.py',
    'setup.cfg',
    'requirements.txt',
    'Pipfile',
    '.git',
  },
  init_options = {
    settings = {
      args = {},
    },
  },
  settings = {
    logLevel = 'debug',
  },
}
