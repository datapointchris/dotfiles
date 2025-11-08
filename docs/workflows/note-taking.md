# Note Taking with nb

This guide covers the note-taking workflows using [nb](https://github.com/xwmx/nb), a git-backed command-line note-taking system.

## Overview

nb provides a unified interface for multiple git-backed markdown notebooks, supporting wiki-style linking, full-text search, and visual browsing.

### Notebook Structure

Three notebooks serve different purposes:

**learning** - Public repository for semester-based learning

```text
~/.nb/learning/ (https://github.com/datapointchris/learning.git)
├── 2024-fall/
│   ├── computer-science/{algorithms, data-structures, databases}
│   ├── systems/{unix, networking}
│   └── readings/{papers, books}
└── 2025-spring/
    ├── computer-science/
    └── philosophy/
```text

**notes** - Private repository for general notes

```text
~/.nb/notes/ (https://github.com/datapointchris/notes.git)
├── work/
├── personal/
└── projects/
```text

**ideas** - Private repository for quick capture

```text
~/.nb/ideas/ (https://github.com/datapointchris/ideas.git)
(flat structure for quick capture)
```text

## Basic Commands

### Navigation

```bash
nb                          # Interactive menu (current notebook)
nb notebooks                # List all notebooks
nb use learning             # Switch to learning notebook
nb learning:                # List notes in learning notebook
nb notes:work/              # List notes in notes/work/ folder
```text

### Creating Notes

```bash
nb add                      # Interactive note creation (opens $EDITOR)
nb add "Title"              # Quick note with title
nb learning:add "Topic"     # Add to specific notebook
nb notes:work/add "Meeting" # Add to specific folder
```text

**Examples:**

```bash
# Add to current semester's CS notes
nb learning:2024-fall/computer-science/add "Binary Search Trees"

# Quick work note
nb notes:work/add "Team Meeting Notes"

# Capture an idea
nb ideas:add "AI-powered search feature"
```text

### Searching

```bash
nb search "algorithm"       # Search current notebook
nb search "database" --all  # Search all notebooks
nb list --query "pattern"   # List matching notes
```text

**Advanced search:**

```bash
# Case-insensitive search
nb search "binary tree" -i

# Search with regex
nb search "algorithm.*complexity"

# Search in specific notebook
nb learning:search "normalization"

# Limit results
nb search "database" --limit 10
```text

### Editing

```bash
nb edit 1                   # Edit note by ID
nb edit algorithm           # Edit by title/keyword
nb learning:edit 3          # Edit in specific notebook
```text

### Viewing

```bash
nb show 1                   # Show note content
nb show --print             # Print to stdout (for piping)
nb browse --gui             # Visual interface in browser
nb browse learning:         # Browse specific notebook
```text

## Cross-Notebook Wiki Links

nb supports wiki-style linking across notebooks, enabling connections between learning, work, and ideas.

### Link Syntax

**Same notebook:**

```markdown
[[file-name]]
[[folder/file-name]]
```text

**Different notebook:**

```markdown
[[notebook:folder/file-name]]
```text

### Examples

**In a learning note (learning:2024-fall/computer-science/databases/normalization.md):**

```markdown
# Database Normalization

## Overview
Database normalization is the process of organizing data to reduce redundancy.

## Forms
- 1NF: Atomic values
- 2NF: No partial dependencies
- 3NF: No transitive dependencies

## Related Topics
- [[data-structures/trees]]  # Same notebook
- [[algorithms/search]]      # Same notebook

## Real-World Application
See my work project: [[notes:work/database-design]]

## Further Reading
- [[readings/papers/codd-relational-model]]
```text

**In a work note (notes:work/database-design.md):**

```markdown
# Database Design Project

## Context
Redesigning the user database schema for better query performance.

## Learning References
- [[learning:2024-fall/computer-science/databases/normalization]]
- [[learning:2024-fall/computer-science/databases/indexing]]

## Implementation Notes
Applied 3NF to user tables, created composite indexes on frequently queried fields.

## Ideas
See related brainstorming: [[ideas:database-optimization]]
```text

**In an ideas note (ideas:database-optimization.md):**

```markdown
# Database Optimization Ideas

## Potential Improvements
- Implement read replicas for heavy query load
- Add caching layer with Redis
- Partition large tables by date

## Research Needed
- [[learning:2024-fall/computer-science/databases/partitioning]]
- [[notes:work/database-design]] (current implementation)
```text

## Git Sync Workflow

Each notebook is independently version-controlled with its own git repository.

### Manual Sync

```bash
# Sync specific notebook
nb learning:sync            # Add, commit, push learning
nb notes:sync               # Sync notes
nb ideas:sync               # Sync ideas

# Check status before syncing
nb learning:status          # Git status for learning
nb notes:git log --oneline  # Recent commits in notes
```text

### Automatic Sync

Configure auto-sync per notebook:

```bash
# Enable auto-sync (commits and pushes on each operation)
nb learning:settings auto_sync on

# Disable auto-sync (manual control)
nb learning:settings auto_sync off
```text

!!! warning "Auto-sync Considerations"
    Auto-sync commits after each `add`, `edit`, or `delete` operation. This is convenient but creates many small commits. For learning notes (public repo), consider manual sync to group related changes.

### Commit Messages

nb auto-generates commit messages:

```text
Add: Binary Search Trees.md
Update: normalization.md
Delete: old-notes.md
```text

For custom commit messages, use git directly:

```bash
cd ~/.nb/learning
git add .
git commit -m "Add complete database normalization notes with examples"
git push
```text

## Daily Workflows

### Morning Study Session

```bash
# Switch to learning context
nb use learning

# Review recent notes
nb learning:list

# Add today's learning topic
nb learning:2024-fall/computer-science/add "Graph Algorithms"

# Edit and expand with cross-links
nb edit graph-algorithms
# In note: [[data-structures/graphs]], [[algorithms/search]]
```text

### Work Context

```bash
# Switch to work notes
nb use notes

# Create meeting notes
nb notes:work/add "Sprint Planning Meeting"

# Reference learning materials
# In note: [[learning:2024-fall/computer-science/algorithms/complexity]]
```text

### Quick Idea Capture

```bash
# Capture idea without switching context
nb ideas:add "Real-time collaboration feature"

# Later, link from project notes
nb notes:projects/add "New Feature Proposals"
# In note: [[ideas:real-time-collaboration-feature]]
```text

### Cross-Reference Workflow

```bash
# While studying algorithms, reference work project
nb learning:2024-fall/computer-science/algorithms/add "Search Optimization"
# In note: Applied in [[notes:work/search-feature]]

# In work notes, link back to learning
nb notes:work/edit search-feature
# In note: Theory: [[learning:2024-fall/computer-science/algorithms/search-optimization]]
```text

## Composition with Other Tools

nb follows the Unix philosophy - it outputs clean data that composes with other tools.

### Interactive Selection with fzf

```bash
# Browse notes interactively
nb list --all | fzf --preview 'nb show {1}'

# Search and select
nb search "algorithm" | fzf | xargs nb show

# Edit note selected with fzf
nb list | fzf | awk '{print $1}' | xargs nb edit
```text

### Notebook Selection with gum

```bash
# Choose notebook with gum
NOTEBOOK=$(nb notebooks | gum choose)
nb use "$NOTEBOOK"

# Add note with gum input
TITLE=$(gum input --placeholder "Note title")
nb add "$TITLE"
```text

### Integration with menu

The `menu` launcher includes nb:

```bash
menu launch
# Select "Take/find a note"
# Launches nb interactive interface
```text

### Scripting

```bash
# Daily note script
#!/bin/bash
TODAY=$(date +%Y-%m-%d)
nb notes:work/add "Daily Log - $TODAY"

# Batch processing
#!/bin/bash
nb search "TODO" --all | while read -r note; do
  echo "Pending task in: $note"
done
```text

## Advanced Workflows

### Semester Rotation

When starting a new semester:

```bash
# Create new semester folder
cd ~/.nb/learning
mkdir -p 2025-spring/computer-science
mkdir -p 2025-spring/philosophy

# Add first note
nb learning:2025-spring/computer-science/add "Distributed Systems"

# Sync structure
nb learning:sync
```text

### Migrating from Obsidian

```bash
# Copy markdown files (preserves [[wiki links]])
cp -r ~/Documents/notes/learning/* ~/.nb/learning/

# Add to git
cd ~/.nb/learning
git add .
git commit -m "Migrate learning notes from Obsidian"
git push

# Update wiki links to cross-notebook format if needed
# [[work/project]] → [[notes:work/project]]
```text

### Visual Browsing

```bash
# Launch web interface
nb browse --gui

# Browse specific notebook
nb browse learning:

# Browse specific folder
nb browse learning:2024-fall/computer-science/
```text

The browser interface provides:

- Visual navigation of folder hierarchy
- Rendered markdown preview
- Clickable wiki links (including cross-notebook)
- Search interface
- Edit links to open in $EDITOR

### Tags and Metadata

nb supports tags and metadata in notes:

```markdown
---
tags: algorithms, study, binary-search
created: 2024-11-07
updated: 2024-11-07
---

# Binary Search

Content here...
```text

Search by tags:

```bash
nb search --tags algorithms
nb list --tags study,algorithms  # Multiple tags
```text

## Tips and Best Practices

### 1. Consistent Folder Structure

Maintain parallel structure across semesters:

```text
2024-fall/computer-science/algorithms/
2024-fall/computer-science/data-structures/
2025-spring/computer-science/algorithms/
2025-spring/computer-science/data-structures/
```text

This makes cross-semester linking predictable.

### 2. Descriptive Filenames

Use clear, descriptive filenames:

```bash
# Good
binary-search-trees.md
database-normalization-forms.md
project-kickoff-meeting-2024-11-07.md

# Avoid
bst.md
db.md
meeting.md
```text

### 3. Liberal Cross-Linking

Link freely between notes - nb makes it easy:

```markdown
Related: [[other-topic]], [[notes:work/project]], [[ideas:feature-idea]]
```text

### 4. Git Sync Rhythm

For public learning repo:

- Manual sync to group related changes
- Meaningful commit messages

For private notes/ideas:

- Auto-sync for convenience
- Less concern about commit granularity

### 5. Notebook Switching

Use `nb use` to set context:

```bash
# Morning: Learning mode
nb use learning

# Afternoon: Work mode
nb use notes

# Quick idea capture (without switching)
nb ideas:add "Quick thought"
```text

### 6. Search First, Create Second

Before creating a new note:

```bash
# Check if topic already exists
nb search "binary search tree" --all

# If found, add to existing note
# If not, create new
```text

## Troubleshooting

### Links Not Resolving

If cross-notebook links don't work:

```bash
# Check notebook exists
nb notebooks

# Verify path
nb notes:work/  # Should list notes

# Check link syntax
[[notes:work/file-name]]  # Correct
[[notes/work/file-name]]  # Incorrect
```text

### Sync Conflicts

If git sync fails:

```bash
cd ~/.nb/learning
git status
git pull --rebase
# Resolve conflicts in $EDITOR
git add .
git rebase --continue
git push
```text

### Missing Notes in Search

If search doesn't find notes:

```bash
# Rebuild index
nb index rebuild

# Search all notebooks
nb search "query" --all
```text

## Related Documentation

- [Quick Reference](../reference/quick-reference.md) - All workflow tools
- [Tool Composition](../architecture/tool-composition.md) - How tools work together
- [nb Official Documentation](https://github.com/xwmx/nb) - Complete nb reference
- Planning documents:
  - `planning/phase2-complete-summary.md` - nb setup details
  - `planning/dotfiles-system-redesign-2025-11.md` - Overall system design
