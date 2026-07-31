-- Python Language Server (basedpyright)
-- Using Ruff for linting, formatting, and organizing imports

return {
  cmd = { 'basedpyright-langserver', '--stdio' },
  filetypes = { 'python' },
  root_markers = {
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
    'requirements.txt',
    'Pipfile',
    'pyrightconfig.json',
    '.git',
  },
  settings = {
    basedpyright = {
      -- Using Ruff's import organizer
      disableOrganizeImports = true,
    },
    python = {
      analysis = {
        -- Ignore all files for analysis to exclusively use Ruff for linting.
        -- Only reaches the server when the project has no [tool.basedpyright]
        -- or [tool.pyright] section; a config file discards this whole table,
        -- so per-rule silencing belongs in pyproject.toml, never here.
        ignore = { '*' },
      },
    },
  },
}
