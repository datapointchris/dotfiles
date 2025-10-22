-- JSON Language Server
local schemas = {}
local has_schemastore, schemastore = pcall(require, 'schemastore')
if has_schemastore then schemas = schemastore.json.schemas() end

return {
  cmd = { 'vscode-json-language-server', '--stdio' },
  filetypes = { 'json', 'jsonc' },
  root_markers = { 'package.json', '.git' },
  init_options = {
    provideFormatter = true,
  },
  settings = {
    json = {
      schemas = schemas,
      validate = { enable = true },
    },
  },
}
