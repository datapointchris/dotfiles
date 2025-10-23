-- Docker Language Server
return {
  cmd = { 'docker-language-server', '--stdio' },
  filetypes = { 'dockerfile' },
  root_markers = { 'Dockerfile', '.git' },
  settings = {},
}
