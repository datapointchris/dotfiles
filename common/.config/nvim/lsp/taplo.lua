-- TOML Language Server
return {
  cmd = { 'taplo', 'lsp', 'stdio' },
  filetypes = { 'toml' },
  root_markers = { '*.toml', '.git' },
  settings = {},
}
