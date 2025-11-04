# Corporate Environment

Solutions for corporate environments with restricted internet access.

## Native LSP Advantage

This configuration uses native Neovim LSP, not Mason, which bypasses most corporate restrictions:

- No dependency on raw.githubusercontent.com
- Direct tool installation via system package managers
- Offline capable after initial setup

## Installation

Install language servers manually using approved package managers:

**TypeScript/JavaScript**:

```sh
npm install -g typescript typescript-language-server
```

**Python**:

```sh
pip install --user basedpyright ruff
```

**JSON/HTML/CSS**:

```sh
npm install -g vscode-langservers-extracted
```

**Bash**:

```sh
npm install -g bash-language-server
```

**Lua**:

```sh
brew install lua-language-server  # macOS
```

## Offline Installation

**Download packages at home**:

```sh
npm pack typescript typescript-language-server
npm pack bash-language-server
# Transfer files to work machine
npm install -g ./typescript-x.x.x.tgz
```

**Use company package mirrors**:

```sh
npm config set registry http://npm.company.com/
pip config set global.index-url http://pypi.company.com/simple/
```

## Configuration

Disable features requiring internet access:

```lua
-- Disable plugin auto-updates
lazy = {
  checker = { enabled = false },
  change_detection = { enabled = false },
}

-- Disable AI features if APIs blocked
codecompanion = { enabled = false },
copilot = { enabled = false },
```

## Troubleshooting

**npm install fails**:

```sh
npm config set registry http://npm.company.com/
```

**Git clone fails**:

```sh
git config --global url."https://github.com/".insteadOf "git@github.com:"
```

**SSL certificate errors**:

```sh
npm config set strict-ssl false
# Better: use company certificate
git config --global http.sslcainfo /path/to/company-cert.pem
```

## Verification

```sh
# Check language servers installed
which typescript-language-server
which basedpyright

# Test in Neovim
nvim test.js
# In Neovim: :LspInfo
```

## Minimal Setup

If full setup is too complex, use minimal native LSP:

```lua
-- No external dependencies, just native LSP
vim.lsp.config.ts_ls = {
  cmd = { 'typescript-language-server', '--stdio' },
  filetypes = { 'typescript', 'javascript' },
}

vim.lsp.config.basedpyright = {
  cmd = { 'basedpyright-langserver', '--stdio' },
  filetypes = { 'python' },
}

vim.lsp.enable({ 'ts_ls', 'basedpyright' })
```
