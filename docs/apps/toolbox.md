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
```

## Registry

The tool registry lives in this repo at `configs/common/.config/toolbox/registry.yml` (symlinked to `~/.config/toolbox/registry.yml`). Edit it to add or update tool entries:

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

## Installation

Defined in `packages.yml` under `go_tools` — installed automatically via `go install github.com/datapointchris/toolbox@latest`.
