---
icon: material/notebook
---

# Notes

A thin wrapper over [zk](https://github.com/zk-org/zk) for the notebook `zk` is
configured against. `notes --help` lists the verbs; `zk --help` covers everything the
wrapper does not wrap, and the upstream docs are the reference for query syntax
and templates.

The wrapper exists for one reason: zk's useful invocations are long
(`zk list --interactive --sort modified`), and four of them get used constantly.
Anything beyond those four is a sign to call `zk` directly rather than to grow
this script.

## Where the notebook lives

At the path `zk`'s own config names, outside this repo. It is replicated between
machines rather than versioned, which is why it is not a git repo. This repo
configures the notebook and never carries its contents.

zk's configuration is `configs/common/.config/zk/config.toml`, symlinked to
`~/.config/zk/`. Its `[group.*]` blocks define per-section note templates and
filename formats.
