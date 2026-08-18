# Custom Installers

`custom_installers` is not a category of tool. It is the name for *no shared
mechanism*: every entry arrives by a route nothing else in the repo uses, so every
entry is its own function in `src/dotfiles/providers/custom.py`. That module
docstring lists the routes and what converging means for each. This page holds the
decisions it does not.

## Check that it really is custom before writing one

A tool with a GitHub release is a `github_releases` entry. It gets checksum
verification, offline bundling and currency measurement for free, and a function
here inherits none of those. Reach for this section only when the bytes genuinely
come from somewhere else.

## The version and the bytes come from different places

An entry declares `repo:` even where nothing is downloaded from GitHub. The repo is
where the *version* lives, which stays a declarative fact even when the
distribution is not. That is what lets `dotfiles check` say a custom installer is
behind, rather than treating presence as the whole verdict.

## Every host an installer reaches is declared by the installer itself

`custom.sources()` answers where a given tool is fetched from.
`network._custom_installer_probes` is its only caller, so the connectivity probe
asks each installer rather than switching on a declared kind. The probe results
carry the answer per tool:

```bash
dotfiles network check --json | jq -r '.probes[] | select(.name == "theme") | .target'
```

## What is deliberately absent

**Rejected: a `--print-url` protocol.** Having the offline bundler ask each script
over a pipe which file to fetch puts the staged filename in two places. The
declaration's `install_url` is the one place. Two answers can drift apart, and the
bundle then holds a file the install never looks for.

**Rejected: a shared "run a vendor script" abstraction beyond staging it.** Several
functions run one, and all they share is where the script comes from — the offline
bundle if it holds one, the network otherwise. What each does with the result
differs enough that a common wrapper would be branches.

**Rejected: a structured failure-log protocol.** Scripts emitting `FAILURE_MANUAL`
blocks for a wrapper to collect puts the log format in as many places as there are
installers. Each function returns a `Result` and the stage writes the log.
