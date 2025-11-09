# Note Taking with zk

This guide covers note-taking workflows using [zk](https://github.com/zk-org/zk), a plain text note-taking assistant with strong markdown and linking support.

## Overview

Single notebook with selective git tracking and auto-discovery of note sections.

**Philosophy**:

- One notebook (`~/notes`) for everything
- Organized by top-level directories (sections)
- Git tracks only `devnotes/` and `learning/` (public/work)
- Personal content (`journal/`, `ideas/`, etc.) stays iCloud-only
- `notes` CLI wrapper for quick access, `zk` directly for advanced features

**Location**: `~/notes` → `~/Documents/notes` (iCloud synced)

## Notebook Structure

```text
~/notes/
├── journal/      # Daily entries (iCloud only)
├── learning/     # Study notes (git tracked, public repo)
├── devnotes/     # Work notes (git tracked, private repo)
├── ideas/        # Quick capture (iCloud only)
├── projects/     # Project planning (iCloud only)
├── dreams/       # Dream journal (iCloud only)
└── .zk/
    ├── config.toml
    └── templates/
```

## Quick Start

### Using the notes CLI Wrapper

The `notes` command provides an interactive menu with auto-discovery:

```bash
# Interactive menu - shows all available sections
notes

# Create note in specific section
notes journal
notes devnotes
notes learning
```

The menu shows:

- Browse recent notes
- Search all notes
- Quick note creation for each discovered section

### Using zk Directly

For advanced features, use `zk` commands directly:

```bash
# Create notes using aliases (from config.toml)
zk journal "Daily standup thoughts"
zk devnote "Debugging authentication flow"
zk learn "Understanding B-trees"
zk idea "App feature concept"

# Browse and search
zk list                           # List all notes
zk list --sort modified-          # Recent notes
zk edit --interactive             # Pick note to edit
zk edit --limit 1 --sort modified-  # Edit last modified

# Search content
zk list --match "authentication"  # Find notes about auth
zk list --created-after "today"   # Notes created today
zk list --group devnotes          # Only work notes
```

## Common Workflows

### Daily Journal Entry

Using notes CLI:

```bash
notes journal
# Opens gum input for title, then creates timestamped entry
```

Using zk directly:

```bash
zk journal "Friday reflections"
# Creates: 2025-11-08-Friday-14:30-friday-reflections.md
```

The journal template includes:

- Date frontmatter
- Entry section
- Tags section

### Work/Dev Notes

```bash
# Quick way
notes devnotes

# Or with zk alias
zk devnote "API endpoint refactoring"
# Creates: 2025-11-08-api-endpoint-refactoring.md
```

Git tracks these automatically, so they sync to your notes repository.

### Learning Notes

```bash
zk learn "Database indexing strategies"
# Creates: 2025-11-08-database-indexing-strategies.md
```

These are also git-tracked for building a public learning repository.

### Quick Idea Capture

```bash
notes ideas
# Or: zk idea "Mobile app feature"
```

Perfect for fleeting thoughts - iCloud-backed but not in git.

### Browse Recent Work

```bash
# Last 20 modified notes
zk recent

# Today's notes
zk today

# Recent devnotes only
zk devnotes-list

# Interactive picker
zk edit --interactive
```

### Search Notes

```bash
# Search by content
zk list --match "authentication"
zk list --match "react hooks"

# Search with interactive edit
zk edit --interactive --match "API"

# Full-text search (if fzf preview is configured)
zk list | fzf --preview 'bat -p {-1}'
```

## Wiki-Style Linking

zk supports wiki-links between notes:

```markdown
# In a note about authentication

See [[jwt-tokens]] for token handling details.
Related: [[api-security]], [[session-management]]
```

The zk LSP integration provides:

- Autocomplete for note links
- Dead link detection
- Link following in editors (Neovim, VS Code)

## Git Workflow

Only `devnotes/` and `learning/` are tracked:

```bash
cd ~/notes

# Check what's tracked
git status

# Commit work notes
git add devnotes/ learning/
git commit -m "notes: add API authentication learnings"
git push
```

Personal sections (`journal/`, `ideas/`, etc.) are in `.gitignore` and stay iCloud-only.

## Templates

Templates live in `~/notes/.zk/templates/`:

- `daily.md` - Journal entries with date and tags
- `devnote.md` - Work notes with project context
- `learning.md` - Study notes with resources section
- `idea.md` - Quick capture template
- `project.md` - Project planning structure
- `dream.md` - Dream journal format

Edit templates to customize note structure:

```bash
cd ~/notes/.zk/templates
nvim daily.md
```

## Configuration

zk config at `~/.config/zk/config.toml` defines:

- **Groups**: Organize notes by directory (journal, devnotes, etc.)
- **Aliases**: Quick commands (`zk journal`, `zk learn`)
- **Templates**: Per-group note formats
- **LSP**: Editor integration settings

See `platforms/common/.config/zk/config.toml` in the dotfiles repo.

## Advanced Usage

### Custom Searches

```bash
# Notes modified in last 7 days
zk list --modified-after "7 days ago"

# Notes by group and date range
zk list --group devnotes --created-after "2025-11-01"

# Interactive edit with filters
zk edit --interactive --group learning --match "database"
```

### Integration with Other Tools

```bash
# Open random note for review
zk edit --limit 1 --sort random

# List notes as JSON for scripting
zk list --format json

# Create note from stdin
echo "# Quick Note\n\nContent here" | zk new --title "Generated"
```

### Batch Operations

```bash
# List notes and pipe to other tools
zk list --format path | xargs grep "TODO"

# Count notes by section
for section in journal learning devnotes ideas; do
  count=$(zk list --group $section | wc -l)
  echo "$section: $count notes"
done
```

## Setup

For initial setup instructions, see [Notes System Setup](../development/notes-system-setup.md).

**Prerequisites**:

- zk installed (`brew install zk`)
- gum installed (`brew install gum`) - for notes CLI interactive menus
- bat installed (`brew install bat`) - for preview formatting

## Tips

**Auto-discovery**: The `notes` CLI automatically discovers new sections. Create any directory in `~/notes/` and it appears in the menu.

**Editor Integration**: Configure your editor for zk LSP support to get link completion and navigation.

**Backup Strategy**:

- Git-tracked sections (devnotes/, learning/) backed up to GitHub
- Personal sections (journal/, ideas/) backed up to iCloud
- Full notebook available on all devices via iCloud

**Quick Access**: Add shell aliases for frequent operations:

```bash
# In your .zshrc
alias jot='zk journal'
alias note='zk devnote'
alias til='zk learn'
```

## Reference

**notes CLI**: `apps/common/notes`
**zk Config**: `platforms/common/.config/zk/config.toml`
**Setup Guide**: `docs/development/notes-system-setup.md`
**zk Documentation**: <https://zk-org.github.io/zk/>
