---
icon: material/notebook
---

# Notes

Plain-text note-taking with zk. Create journal entries, dev notes, and learning documentation without leaving the terminal. Link notes with wiki-links, organize with sections, and back up with git or iCloud.

## Quick Start

```bash
notes                      # Interactive menu
notes search              # Full-text search
notes new                 # Create note (pick section)
notes recent              # Browse recent notes
notes browse              # Browse by section

# Direct zk access
zk journal "Daily standup"     # Create journal entry
zk devnote "Bug fix notes"     # Create dev note
zk learn "Database indexing"   # Create learning note
```

## Commands

### Notes CLI Wrapper

- `notes` - Show help and available commands
- `notes search` - Full-text search with live preview (fzf + ripgrep)
- `notes new [section]` - Create note with guided section selection
- `notes recent` - Browse 50 most recently modified notes
- `notes browse` - Browse notes by section

The notes CLI provides an interactive interface with auto-discovery of notebook sections. It wraps zk for common workflows.

### Direct ZK Commands

**Create notes:**

- `zk journal "title"` - Create journal entry with date
- `zk devnote "title"` - Create development note
- `zk learn "title"` - Create learning note

**List and search:**

- `zk list` - List all notes
- `zk list --match "keyword"` - Search notes by content
- `zk list --sort modified-` - Recent notes first
- `zk list --group devnotes` - Filter by section
- `zk list --tag "python"` - Filter by tag

**Edit notes:**

- `zk edit --interactive` - Browse and select note to edit
- `zk edit --match "database"` - Edit notes matching search

**Link management:**

- `zk list --link-to "note.md"` - Find notes linking to this note
- `zk list --linked-by "note.md"` - Find notes linked from this note

## Notebook Structure

Single notebook at `~/notes` (synced to `~/Documents/notes` via iCloud):

```text
~/notes/
├── journal/      # Daily entries (iCloud only)
├── learning/     # Study notes (git tracked, public)
├── devnotes/     # Work notes (git tracked, private)
├── ideas/        # Quick capture (iCloud only)
├── projects/     # Project planning (iCloud only)
├── dreams/       # Dream journal (iCloud only)
└── .zk/
    ├── config.toml
    └── templates/
```

**Backup strategy:**

- Git tracks `devnotes/` and `learning/` (pushed to GitHub)
- Personal sections (`journal/`, `ideas/`, etc.) stay iCloud-only
- Full notebook available on all devices

## How It Works

The notes CLI auto-discovers sections by scanning `~/notes/` directories. Each section gets its own menu option. Direct zk commands provide full functionality.

### Configuration

**zk config:** `~/.config/zk/config.toml`

Defines:

- Groups: Organize notes by directory
- Aliases: Quick commands (zk journal, zk learn)
- Templates: Per-group note formats
- LSP: Editor integration for link completion and navigation

**notes CLI:** `apps/common/notes` (bash wrapper around zk)

### Templates

Templates live in `~/notes/.zk/templates/`:

- `daily.md` - Journal entries with date
- `devnote.md` - Work notes with context
- `learning.md` - Study notes with resources
- `idea.md` - Quick capture format
- `project.md` - Project planning structure

Edit templates to customize note structure:

```bash
cd ~/notes/.zk/templates
nvim daily.md
```

### Wiki-Links

Link notes with wiki-link syntax:

```markdown
See [[jwt-tokens]] for details.
Related: [[api-security]], [[session-management]]
```

The zk LSP provides:

- Autocomplete for note links
- Dead link detection
- Link following in editors (Neovim, VS Code)

## Workflow

Daily journal entry:

```bash
notes journal
# Or: zk journal "Friday reflections"
```

Quick dev note:

```bash
notes new dev
# Or: zk devnote "API endpoint refactoring"
```

Search across all notes:

```bash
notes search
# Type to filter, preview shows context
```

Browse recent work:

```bash
notes recent
# Or: zk edit --interactive
```

Find related notes via links:

```bash
zk list --link-to "database.md"
```

## Git Workflow

Only `devnotes/` and `learning/` are tracked:

```bash
cd ~/notes
git status
git add devnotes/ learning/
git commit -m "notes: add API authentication learnings"
git push
```

Personal sections are in `.gitignore` and stay iCloud-only.

## Advanced Usage

Custom searches:

```bash
zk list --modified-after "7 days ago"
zk list --group devnotes --created-after "2025-11-01"
zk edit --interactive --group learning --match "database"
```

Batch operations:

```bash
zk list --format path | xargs grep "TODO"
```

Shell aliases for quick access:

```bash
alias jot='zk journal'
alias note='zk devnote'
alias til='zk learn'
```

## Initial Setup

**Prerequisites:**

- zk (`brew install zk`)
- gum (`brew install gum`) - for interactive menus
- bat (`brew install bat`) - for preview formatting

**Create symlink for convenience:**

```bash
ln -s ~/Documents/notes ~/notes
```

**Initialize git tracking:**

```bash
cd ~/Documents/notes
git init

# Create gitignore for selective tracking
cat > .gitignore << 'EOF'
# Personal content - iCloud only
journal/
ideas/
projects/
dreams/

# System files
.DS_Store
.zk/cache/
EOF

git add .
git commit -m "feat: initialize notes repository"
git remote add origin git@github.com:yourusername/notes.git
git push -u origin main
```

**Create directory structure:**

```bash
cd ~/notes
mkdir -p journal learning devnotes ideas projects dreams .zk/templates
```

Templates are created in `.zk/templates/` for each note type (journal, devnote, learning, idea, project, dream). Each template defines the frontmatter and structure for that note type.

## At Work

Clone your notes repository on a work machine to access `devnotes/` and `learning/`:

```bash
git clone git@github.com:yourusername/notes.git ~/notes

# Result:
# - devnotes/ and learning/ with full content
# - Empty personal directories (gitignored)
# - All wikilinks between devnotes and learning work
# - Links to personal notes show as dead links (expected)

# Add work notes
zk devnote "Production deployment"
git add devnotes/
git commit -m "docs: add deployment notes"
git push
```

Personal sections remain iCloud-only on your personal devices.

## Future Enhancements

**URL Capture:** Create a quick-capture tool to grab URLs from clipboard and create notes:

```bash
#!/usr/bin/env bash
# ~/bin/capture-url
url=$(pbpaste)
title=$(gum input --placeholder "Title")
section=$(gum choose "ideas" "devnotes" "learning")
zk "$section" "$title" <<< "URL: $url"
```

Bind to keyboard shortcut for instant capture.

## See Also

- [zk Documentation](https://zk-org.github.io/zk/) - Full zk reference
- [Menu](menu.md) - Quick access to workflow tools
