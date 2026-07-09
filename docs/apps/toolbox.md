---
icon: material/toolbox
---

# Toolbox

CLI tool discovery for the installed toolchain. Source: [datapointchris/toolbox](https://github.com/datapointchris/toolbox).

```bash
toolbox list             # All tools by category
toolbox show bat         # Details for a specific tool
toolbox search git       # Search by name, description, or tags
toolbox categories       # Interactive category browser
toolbox funcs            # Annotated shell functions (#@name / #-->desc)
toolbox aliases          # Shell aliases with descriptions
toolbox check            # Drift check: registry vs PATH vs disk
toolbox remind           # Surface a forgotten tool/function/alias (shell startup)
```

## Registry

The tool registry lives at `~/dev/tools.yml` (override with `$TOOLBOX_REGISTRY`). It is Syncthing-synced *data*, not part of this repo — the dev paths (`~/tools`, `~/dotfiles`) don't exist on every machine, but `~/dev` does. Edit it to add or update tool entries:

```yaml
new-tool:
  category: utility
  description: "What it does"
  installed_via: brew
  usage: "new-tool [options]"
  why_use: "Why this over alternatives"
  examples:
    - cmd: "new-tool --example"
      desc: "Example usage"
  see_also: [related-tool]
  tags: [tag1, tag2]
  docs_url: "https://..."
```

## Rediscovery — `toolbox remind`

Finding a tool once doesn't stop you forgetting it. `remind` is the retention half: it surfaces one
thing you own but have let go cold, so neglected shortcuts cycle back into awareness.

The candidate pool spans **everything you own** — registry tools, annotated shell functions, shell
aliases, git aliases, and forgit's fzf-git shortcuts. From that pool it picks the one **reminded
least recently that you have not run in the last 90 days**, then advances its own history so it
round-robins through the whole set rather than repeating. State lives in
`~/.local/state/toolbox/reminders.json`; the 90-day recency check reads your zsh history, so it needs
`setopt EXTENDED_HISTORY`. Git aliases (invoked as `git <name>`) are matched on the second history
word so they count as used.

`remind` is not wired into shell startup directly. It surfaces through the `menu review` register: the
`revisit-a-tool` item runs it (`show: toolbox remind`) when that review comes due, so a forgotten
shortcut appears as part of your cadence rather than on every shell. See [Menu](menu.md).

## Installation

Defined in `packages.yml` under `go_tools` — installed automatically via `go install github.com/datapointchris/toolbox@latest`.
