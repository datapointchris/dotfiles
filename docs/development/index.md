---
icon: material/code-braces
---

# Development

Contributing to and testing dotfiles.

Language standards for the Go applications here live on the hub:
[Go Development](https://docs.ichrisbirch.com/go/go-development/),
[Go Quick Reference](https://docs.ichrisbirch.com/go/go-quick-reference/),
[Bubbletea](https://docs.ichrisbirch.com/go/bubbletea-quick-reference/).

The shell libraries that scripts here source — logging, formatting, the help
grammar, feature flags, error traps — are in
[Shell Libraries](../architecture/shell-libraries.md).

## Pages

- [VM Testing](testing.md) — the test tiers, defined by what a test may touch, and the three axes
  that place one
- [Publishing Docs](publishing-docs.md) — the workflow that builds this site and pushes `gh-pages`,
  and why a second publisher breaks it
- [Docs Audit Record](docs-audit.md) — a snapshot of one documentation audit: what was found wrong,
  and the measurements to compare against next time. Add below it, never edit it
