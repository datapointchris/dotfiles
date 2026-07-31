# Pyright Config File Precedence Over LSP Settings

## Problem

A `reportUnannotatedClassAttribute` warning kept appearing in Neovim on a Python project even
after `reportUnannotatedClassAttribute = 'none'` was added to the `basedpyright` LSP settings in
`configs/common/.config/nvim/lsp/basedpyright.lua`. The neighbouring `ignore = { '*' }` — which
should have suppressed every basedpyright diagnostic outright, since Ruff does the linting — was
plainly not taking effect either.

Restarting the server and confirming the settings were in flight (`:checkhealth vim.lsp` shows
each client's resolved `settings` table) changed nothing.

## Solution

Put the rule in the project's `pyproject.toml`:

```toml
[tool.basedpyright]
reportUnannotatedClassAttribute = false
```

Diagnostic rules are top-level keys in the config file, not nested under
`diagnosticSeverityOverrides` the way they are in LSP settings. Accepted values are `false`/`true`
or `"none"`/`"information"`/`"warning"`/`"error"`.

## Key Learnings

- **A project config file discards client settings wholesale.** In `pyright-langserver.js`, once
  a config file is loaded the client's settings are applied only `if (!commandLineOptions.fromLanguageServer)`
  — which is never true for a language server. `ignore`, `exclude`, and `diagnosticSeverityOverrides`
  all ride in that discarded table. This is by design, not a merge conflict: the config file is
  authoritative so the editor and CI agree.
- **"Config file" means the `[tool.pyright]`/`[tool.basedpyright]` section, not the file.** A bare
  `pyproject.toml` with no such section is not a config file, which is why the same LSP settings
  work fine in some repos and are inert in others — the symptom looks machine-specific but is
  project-specific.
- **basedpyright defaults to `recommended`, not `standard`.** The server calls
  `initializeTypeCheckingMode('recommended')` before reading any config, which turns on
  basedpyright-only rules like `reportUnannotatedClassAttribute` that plain pyright never emits.
- **Client settings land under `basedpyright.analysis`, with `python.analysis` as an undocumented
  fallback.** The fallback only fires when `basedpyright.analysis` resolves to nothing, so a
  partially-populated `basedpyright` table can silently shadow the `python` one.
- **Read the `source` and `code` off the diagnostic before chasing config.** With the cursor on the
  line, `:lua =vim.diagnostic.get(0, { lnum = vim.fn.line('.') - 1 })` returns the owning server
  and rule name — Ruff's `ANN*` rules produce near-identical annotation complaints.
