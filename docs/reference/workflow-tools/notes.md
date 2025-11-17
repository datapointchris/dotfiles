# Notes System

The notes system provides fast, frictionless note-taking using zk (a plain-text note-taking tool with wiki-link support). Create journal entries, development notes, and learning documentation without leaving the terminal. Link notes together naturally with wiki-links that work across your entire notebook.

## Why Plain-Text Notes

Note-taking apps come and go. Rich formatting creates lock-in. Proprietary formats become unreadable when companies shut down. Searching requires the app's interface. Backing up needs special tools.

Plain text solves all of this. Notes are markdown files you can read anywhere. Version control with git works naturally. Search with ripgrep is instant. Backup is copying files. The tools never become obsolete because the format is universal.

Zk adds structure without complexity. Wiki-links connect ideas. Templates maintain consistency. Tags organize naturally. Language server integration brings IDE features to markdown. All while keeping notes as simple text files.

## Quick Start

Open the notes menu for interactive commands or create notes directly:

```bash
notes                    # Interactive menu
notes search            # Full-text search
notes new               # Create note (pick section)
notes recent            # Browse recent notes
notes browse            # Browse by section

# Direct zk access
zk journal "Daily standup"     # Create journal entry
zk devnote "Bug fix notes"     # Create dev note
zk learn "Database indexing"   # Create learning note
```

The interactive menu auto-discovers notebook sections and provides guided workflows. Direct zk access gives you full power when you know exactly what you want.

## Commands

### Interactive Menu

Show available commands and help:

```bash
notes
```

Displays all available commands with examples. Use this as a quick reference when you forget syntax.

### Search Notes

Full-text search across all notes with live preview:

```bash
notes search
```

Opens an fzf interface with ripgrep-powered search. Start typing to filter results. Search matches note content, not just titles. Preview shows matching context with syntax highlighting.

Select a note to open it in your editor. Search works across all sections simultaneously.

### Create New Note

Create a note with guided section selection:

```bash
notes new              # Pick section interactively
notes new dev         # Create directly in dev section
```

Without arguments, notes prompts you to select a section using gum. With a section argument, notes skips straight to title input. After entering a title, notes creates the note using the appropriate zk template.

If zk has a custom command for the section (like `zk journal`), notes uses that. Otherwise it creates the note in the specified directory.

### Browse Recent Notes

See the 50 most recently modified notes:

```bash
notes recent
```

Opens fzf with recent notes sorted by modification time. Preview shows note content with syntax highlighting. Select to open in your editor.

This is perfect for continuing work from yesterday or finding that note you just edited.

### Browse by Section

Navigate notes organized by section:

```bash
notes browse
```

First select a section (journal, devnotes, learning, etc). Then browse all notes in that section. Preview shows full note content.

Use this when you know which area to look in but not which specific note.

## Direct ZK Access

The notes command wraps zk for common workflows, but zk provides much more functionality. Use zk directly for full power.

### Create Specific Note Types

Zk supports custom note types via aliases:

```bash
zk journal "Daily standup"         # Create journal entry
zk devnote "API refactoring"       # Create development note
zk learn "Docker networking"       # Create learning note
```

Each alias uses its own template and creates notes in the appropriate section. Templates include metadata like date, tags, and custom frontmatter.

### List Notes

View and filter your notes:

```bash
zk list                           # List all notes
zk list --match "API"            # Search for notes about API
zk list --sort modified-         # Recent notes first
zk list --limit 10               # First 10 notes
```

Combine flags for precise queries. Search works on titles, content, and tags.

### Edit Notes

Browse and edit interactively:

```bash
zk edit --interactive            # Browse and select note to edit
zk edit --match "database"       # Edit notes about database
```

Interactive mode shows a filterable list. Select to open in your editor.

### Link Management

Find and analyze links between notes:

```bash
zk list --link-to "database.md"  # Notes linking to database note
zk list --linked-by "index.md"   # Notes linked from index note
```

This reveals your knowledge graph structure and finds related content.

### Tags

Find notes by tag:

```bash
zk list --tag "python"           # All Python notes
zk list --tag "tutorial"         # All tutorial notes
```

Tags work across sections. Tag a journal entry, a dev note, and a learning note with "python" and find them together.

## Directory Structure

Notes use a single notebook with auto-discovered sections:

```text
~/notes/
├── journal/             # Daily entries (iCloud only)
├── devnotes/            # Work notes (git tracked)
├── learning/            # Study notes (git tracked)
├── ideas/               # Quick capture (iCloud only)
├── projects/            # Project planning (iCloud only)
├── dreams/              # Dream journal (iCloud only)
└── .zk/
    ├── config.toml
    └── templates/
```

Sections are just directories. Create a new directory and it becomes a section automatically. No configuration needed.

### Selective Git Tracking

Some sections sync via iCloud (journal, ideas, dreams) for mobile access. Others track in git (devnotes, learning) for version control. This is configured in `.gitignore` at the notebook level.

Journal entries don't need version history. Development notes benefit from git history and backup. The structure supports both patterns naturally.

## Wiki Links

Connect notes using wiki-link syntax:

```markdown
# In any note
[[jwt-tokens]]
[[folder/file-name]]

# Wiki-links work across all sections
See [[api-security]] for details.
Related: [[session-management]]
```

Wiki-links work across sections automatically. Reference a dev note from a learning note. Link journal entries to projects. The structure is flat - all notes are equally accessible.

### Link Completion

Zk's language server provides autocomplete for wiki-links in Neovim. Type `[[` and see suggestions. Select to insert the link. This makes linking effortless and prevents broken references.

### Following Links

Use Neovim's `gf` (go to file) on a wiki-link to open the target note. Zk configures this automatically. Navigation between notes becomes as simple as clicking links in a browser.

## Templates

Zk templates provide consistent structure for different note types. Edit templates at `~/.zk/templates/`.

### Journal Template

```markdown
---
date: {{date}}
tags: [journal]
---

# {{title}}

{{content}}
```

Journal entries include date and journal tag automatically.

### Dev Note Template

```markdown
---
date: {{date}}
tags: [dev]
---

# {{title}}

## Context

## Solution

## References
```

Dev notes include structure for documenting problems and solutions.

### Learning Template

```markdown
---
date: {{date}}
tags: [learning]
status: in-progress
---

# {{title}}

## Overview

## Key Concepts

## Examples

## Resources
```

Learning notes include sections for concepts, examples, and resources.

Customize templates to match your workflow. Templates are just markdown files with variable placeholders.

## Configuration

Zk configuration lives at `~/.config/zk/config.toml`:

```toml
[notebook]
dir = "~/notes"

[note]
filename = "{{slug}}"
extension = "md"
template = "default.md"

[alias]
journal = "zk new journal --title '$1'"
devnote = "zk new devnotes --title '$1'"
learn = "zk new learning --title '$1'"

[lsp]
completion.enabled = true
```

The `[alias]` section defines custom note types. Add new aliases to create specialized note commands.

## Integration with Neovim

Zk's language server integrates with Neovim for IDE-like features:

- **Autocomplete**: Complete wiki-links, tags, and note titles
- **Go to definition**: Jump to linked notes with `gf`
- **Find references**: See all links to current note
- **Hover**: Preview linked notes inline

Configure zk-lsp in Neovim's LSP setup to enable these features.

## Common Workflows

### Daily Journaling

Create journal entries consistently:

```bash
zk journal "$(date +%Y-%m-%d)"
```

Or bind to a shell alias:

```bash
alias today="zk journal \"$(date +%Y-%m-%d)\""
today  # Opens today's journal
```

### Documenting Code Problems

Capture problems and solutions:

```bash
zk devnote "PostgreSQL query performance"
# Document the problem, investigation, and solution
# Link to related notes: [[database-indexing]]
```

Later, search for similar issues:

```bash
notes search
# Type "postgres" to find all database notes
```

### Learning New Topics

Start a learning note:

```bash
zk learn "Docker Compose"
# Add resources, concepts, examples
# Link to related notes: [[docker-basics]]
```

Find all learning notes:

```bash
zk list --tag learning
```

### Finding Related Information

Search across all notes:

```bash
notes search
# Type your query
# Preview shows matching context
```

Or use zk's structured search:

```bash
zk list --match "authentication" --link-to "security.md"
```

### Connecting Ideas

Link notes naturally while writing:

```markdown
Today I learned about [[database-transactions]]. This relates to
[[acid-properties]] and [[isolation-levels]]. Need to review
[[postgresql-docs]] for specifics.
```

Later, view the knowledge graph:

```bash
zk list --link-to "database-transactions.md"
```

## Best Practices

### Write Notes While Learning

Capture information as you learn it. Don't wait until later - you'll forget context. Open a note when starting research. Add thoughts while reading. Link to sources immediately.

### Link Liberally

Create connections between notes generously. Link to related concepts even if the connection seems obvious. Your knowledge graph becomes more valuable with more links.

### Use Tags Sparingly

Tags are for broad categories (dev, learning, journal). Don't create too many tags or they lose meaning. Wiki-links provide more precise connections.

### Keep Templates Simple

Resist the urge to over-structure templates. Add sections only when you consistently use them. Empty sections create friction.

### Review Recent Notes

Periodically browse recent notes to refresh memory and find connection opportunities:

```bash
notes recent
```

## Troubleshooting

### Zk Not Found

If zk command is missing:

- Install zk: `brew install zk`
- Verify installation: `which zk`
- Check PATH includes Homebrew: `echo $PATH`

### Notes Directory Missing

If notes directory doesn't exist:

- Create notebook: `zk init ~/notes`
- Create initial sections: `mkdir ~/notes/{journal,devnotes,learning}`
- Verify: `ls ~/notes`

### Wiki Links Not Working

If wiki-links don't autocomplete or jump:

- Check zk LSP is configured in Neovim
- Verify config: `cat ~/.config/zk/config.toml`
- Restart Neovim LSP: `:LspRestart`

### Search Not Finding Notes

If notes search returns nothing:

- Check ripgrep is installed: `which rg`
- Verify notes directory: `echo $ZK_NOTEBOOK_DIR`
- Try direct search: `rg "query" ~/notes`

### Templates Not Working

If custom templates aren't used:

- Check template path: `ls ~/.zk/templates/`
- Verify config points to correct template
- Check template syntax (YAML frontmatter, variable placeholders)

## Advanced Usage

### Custom Note Types

Define new note types in config:

```toml
[alias]
meeting = "zk new meetings --title '$1'"
idea = "zk new ideas --title '$1'"
```

Create matching templates at `~/.zk/templates/meetings.md` and `~/.zk/templates/ideas.md`.

### Automated Backups

Notes in git track automatically. For iCloud sections, backup manually:

```bash
#!/usr/bin/env bash
# Backup notes to git (excluding iCloud sections)
cd ~/notes
git add devnotes/ learning/
git commit -m "Notes backup $(date +%Y-%m-%d)"
```

### Note Statistics

Count notes by section:

```bash
find ~/notes -name "*.md" -not -path "*/.*" | \
  awk -F/ '{print $(NF-1)}' | sort | uniq -c
```

### Find Orphaned Notes

List notes with no incoming links:

```bash
# All notes
zk list --format "{{path}}"

# Notes with incoming links
zk list --format "{{path}}" | while read note; do
  zk list --linked-by "$note" --quiet && echo "$note"
done

# Compare to find orphans
```

### Search by Date

Find notes from specific time periods:

```bash
zk list --created-after "2024-01-01"
zk list --modified-before "2023-12-31"
zk list --created-after "last week"
```

## See Also

- [Menu System](menu.md) - Access notes through menu
- [Tool Discovery](toolbox.md) - Find note-related tools
- [Neovim Configuration](/configuration/neovim.md) - Zk LSP integration
