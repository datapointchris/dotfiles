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
        -- Ignore all files for analysis to exclusively use Ruff for linting
        ignore = { '*' },
        diagnosticSeverityOverrides = {
          -- basedpyright-only; demands annotations on every class attribute
          -- unless the class is @final, which is not a decorator worth adding
          reportUnannotatedClassAttribute = 'none',
        },
      },
    },
  },
}
