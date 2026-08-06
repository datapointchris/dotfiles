---
icon: material/notebook
---

# Notes

A thin wrapper over [zk](https://github.com/zk-org/zk) for the `~/notes`
notebook. `notes --help` lists the verbs; `zk --help` covers everything the
wrapper does not wrap, and the upstream docs are the reference for query syntax
and templates.

The wrapper exists for one reason: zk's useful invocations are long
(`zk list --interactive --sort modified`), and four of them get used constantly.
Anything beyond those four is a sign to call `zk` directly rather than to grow
this script.

## Where the notebook lives

`~/notes` is Syncthing-synced between machines, not a git repo and not in
iCloud. It holds Chris's own notes, written for him; `~/obsession` is the
parallel store written for Claude. The distinction is audience, not authorship —
see the directory ecosystem section of `~/.claude/CLAUDE.md`.

zk's configuration is `configs/common/.config/zk/config.toml`, symlinked to
`~/.config/zk/`. Its `[group.*]` blocks define per-section note templates and
filename formats.
