-- Markdown Language Server
return {
  cmd = { 'marksman', 'server' },
  filetypes = { 'markdown', 'markdown.mdx' },
  root_markers = { '.git', '.marksman.toml' },
  settings = {},
}
