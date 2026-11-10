-- `fleet inbox capture note` writes its note as fleet-capture-*.md. A filetype of its
-- own keeps markdown's tree-sitter parser off it, because gc takes its comment
-- string from that parser's language before the buffer's own.
vim.filetype.add({ pattern = { ['.*/fleet%-capture%-[^/]*%.md'] = 'fleetcapture' } })
