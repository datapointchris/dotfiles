-- Amazon States Language Server, for Step Functions definitions
return {
  cmd = { 'asl-language-server', '--stdio' },
  filetypes = { 'asl', 'asl-yaml' },
  root_markers = { '.git' },
}
