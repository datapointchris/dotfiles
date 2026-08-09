---
icon: material/code-braces
---

# Development

Contributing to and testing dotfiles.

- **[Testing](testing.md)** — the tiers, how the shell is tested from pytest, and the Docker-backed installation runs
- **[Publishing Docs](publishing-docs.md)** — how this site deploys, and the one rule about `gh-pages`

Go applications here (`toolbox`, `sesh`) install through `go_tools` in
`install/packages.yml` and are documented per-app under
[Apps](../apps/index.md). Language standards live on the hub:
[Go Development](https://docs.ichrisbirch.com/go/go-development/),
[Go Quick Reference](https://docs.ichrisbirch.com/go/go-quick-reference/),
[Bubbletea](https://docs.ichrisbirch.com/go/bubbletea-quick-reference/).

The shell libraries that scripts here source — logging, formatting, the help
grammar, feature flags, error traps — are in
[Shell Libraries](../architecture/shell-libraries.md).
