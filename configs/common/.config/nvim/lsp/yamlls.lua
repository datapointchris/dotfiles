-- YAML Language Server
return {
  cmd = { 'yaml-language-server', '--stdio' },
  filetypes = { 'yaml', 'yaml.docker-compose', 'yaml.gitlab' },
  root_markers = { '.git' },
  settings = {
    yaml = {
      schemas = {
        ['https://json.schemastore.org/github-workflow.json'] = '/.github/workflows/*',
        ['https://raw.githubusercontent.com/compose-spec/compose-spec/master/schema/compose-spec.json'] = {
          'docker-compose*.yml',
          'docker-compose*.yaml',
          'compose*.yml',
          'compose*.yaml',
        },
        ['https://json.schemastore.org/kustomization.json'] = 'kustomization.yaml',
        ['https://json.schemastore.org/chart.json'] = 'Chart.yaml',
        kubernetes = '*.yaml',
      },
      schemaStore = {
        enable = true,
        url = 'https://www.schemastore.org/api/json/catalog.json',
      },
      validate = true,
      completion = true,
      hover = true,
    },
  },
}
