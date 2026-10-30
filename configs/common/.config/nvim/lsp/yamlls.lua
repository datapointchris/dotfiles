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
      -- mkdocs-material's editor setup lists these, so a mkdocs.yml's python tags resolve
      customTags = {
        '!ENV scalar',
        '!ENV sequence',
        '!relative scalar',
        'tag:yaml.org,2002:python/name:material.extensions.emoji.to_svg',
        'tag:yaml.org,2002:python/name:material.extensions.emoji.twemoji',
        'tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format',
        'tag:yaml.org,2002:python/object/apply:pymdownx.slugs.slugify mapping',
      },
      validate = true,
      completion = true,
      hover = true,
    },
  },
}
