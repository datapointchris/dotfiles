# Custom Installers

`custom_installers` is not a category of tool. It is the name for *no shared
mechanism* — a vendor install script, an S3 bucket with a GPG trust root, a
HashiCorp mirror carrying its own checksums file, and git repos with a build. Each
is one function in `src/dotfiles/providers/custom.py`, whose module docstring is
the account of how each one converges and why no engine fits them. This page holds
the decisions that docstring does not.

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

`sources()` returns each host installing a tool depends on, so the connectivity
probe asks the installer rather than switching on a declared kind. Read them for
any tool:

```bash
dotfiles packages show theme
```

## What is deliberately absent

**Rejected: a `--print-url` protocol.** Having the offline bundler ask each script
for a `name|version|url` line over a pipe puts the staged filename in two places.
The declaration's `install_url` is the one place, and the pipe is a second place
for the bundler and the installer to disagree about which file to stage.

**Rejected: a shared "run a vendor script" abstraction beyond staging it.** Several
functions run one, and all they share is where the script comes from — the offline
bundle if it holds one, the network otherwise. What each does with the result
differs enough that a common wrapper would be branches.

**Rejected: a structured failure-log protocol.** Scripts emitting `FAILURE_MANUAL`
blocks for a wrapper to collect puts the log format in as many places as there are
installers. Each function returns a `Result` and the stage writes the log.
