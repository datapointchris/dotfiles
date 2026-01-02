# Phase 2 Complete - nb Notes & Learning Setup

**Date:** 2025-11-07
**Status:** ✓ Complete

## What Was Accomplished

### 1. nb Notebooks Created

**Notebooks:**

- `learning` - Public repository for semester-based learning (<https://github.com/datapointchris/learning.git>)
- `notes` - Private repository for general notes (<https://github.com/datapointchris/notes.git>)
- `ideas` - Private repository for quick idea capture (<https://github.com/datapointchris/ideas.git>)

**Folder Structure:**

**learning:**

```text
2024-fall/
├── computer-science/
│   ├── algorithms/
│   ├── data-structures/
│   └── databases/
├── systems/
│   ├── unix/
│   └── networking/
└── readings/
    ├── papers/
    └── books/
2025-spring/
├── computer-science/
└── philosophy/
```text

**notes:**

```text
work/
personal/
projects/
```text

**ideas:**

```text
(flat structure for quick capture)
```text

### 2. Git Configuration

All notebooks are git-initialized with remotes configured:

- learning: Public repository
- notes: Private repository
- ideas: Private repository

Each notebook can be independently version controlled while nb treats them as a unified system.

## nb Workflow Guide

### Basic Commands

**Navigation:**

```bash
nb                          # Interactive menu (current notebook)
nb notebooks                # List all notebooks
nb use learning             # Switch to learning notebook
nb learning:                # List notes in learning notebook
nb notes:work/              # List notes in notes/work/ folder
```text

**Creating Notes:**

```bash
nb add                      # Interactive note creation
nb add "Title"              # Quick note with title
nb learning:add "CS Topic"  # Add to specific notebook
nb notes:work/add "Meeting" # Add to specific folder
```text

**Searching:**

```bash
nb search "algorithm"       # Search current notebook
nb search "database" --all  # Search all notebooks
nb list --query "pattern"   # List matching notes
```text

**Editing:**

```bash
nb edit 1                   # Edit note by ID
nb edit algorithm           # Edit by title/keyword
nb learning:edit 3          # Edit in specific notebook
```text

**Viewing:**

```bash
nb show 1                   # Show note content
nb browse --gui             # Visual interface
nb browse learning:         # Browse specific notebook
```text

### Cross-Notebook Wiki Links

nb supports wiki-style linking across notebooks:

**In a learning note:**

```markdown
# Database Normalization

See my work notes: [[notes:work/database-design]]
Related readings: [[readings/papers/codd-relational-model]]
```text

**In a work note:**

```markdown
# Database Design Project

Reference my learning notes: [[learning:2024-fall/computer-science/databases/normalization]]
```text

**Link syntax:**

- Same notebook: `[[file-name]]` or `[[folder/file-name]]`
- Different notebook: `[[notebook:folder/file-name]]`

### Git Sync Workflow

**Manual sync (per notebook):**

```bash
nb learning:sync            # Sync learning notebook
nb notes:sync               # Sync notes notebook
nb ideas:sync               # Sync ideas notebook
```text

**Check status:**

```bash
nb learning:status          # Git status for learning
nb git log --oneline        # Recent commits
```text

**Automatic sync:**
nb can auto-sync on operations (configured per notebook):

```bash
nb learning:settings auto_sync on
```text

### Daily Workflows

**Morning Setup:**

```bash
nb use learning             # Switch to learning context
nb learning:list            # Review recent notes
nb learning:add "Today's topic"
```text

**Work Context:**

```bash
nb use notes                # Switch to work notes
nb notes:work/add "Meeting notes"
```text

**Quick Idea Capture:**

```bash
nb ideas:add                # Quick capture to ideas
nb ideas:search "project"   # Find related ideas
```text

**Cross-Reference:**

```bash
# While in learning notebook, link to work notes
nb add "Database Study"
# In the note: [[notes:work/database-project]]
```text

### Search and Discovery

**Find across all notebooks:**

```bash
nb search "keyword" --all
nb list --query "pattern" --all
nb browse --gui             # Visual browsing
```text

**Tag-based organization:**

```bash
nb add --tags algorithms,study
nb list --tags algorithms
```text

## Examples

### Example 1: Creating a Learning Note with Cross-References

```bash
# Switch to learning notebook
nb use learning

# Create a new note
nb add "Binary Search Trees"

# In the note:
# Binary Search Trees
#
# ## Overview
# [content]
#
# ## Related
# - [[data-structures/trees]]
# - [[algorithms/search]]
# - Work project: [[notes:work/search-optimization]]
# - Paper: [[readings/papers/knuth-searching]]
```text

### Example 2: Work Note Referencing Learning

```bash
# Switch to notes notebook
nb use notes

# Create work note
nb work/add "Database Optimization"

# In the note:
# Database Optimization Project
#
# ## Learning References
# - [[learning:2024-fall/computer-science/databases/indexing]]
# - [[learning:2024-fall/computer-science/databases/normalization]]
#
# ## Implementation Notes
# [content]
```text

### Example 3: Quick Idea Capture

```bash
# From anywhere, capture to ideas
nb ideas:add "AI-powered search feature"

# Later, reference from work notes
nb notes:work/add "New Features"
# In note: See [[ideas:ai-powered-search-feature]]
```text

## Verification

All notebooks operational:

```bash
$ nb notebooks
home
ideas (https://github.com/datapointchris/ideas.git)
learning (https://github.com/datapointchris/learning.git)
notes (https://github.com/datapointchris/notes.git)

$ nb learning:git remote -v
origin  https://github.com/datapointchris/learning.git (fetch)
origin  https://github.com/datapointchris/learning.git (push)
```text

## Integration with Workflow Tools

nb integrates with the workflow tools from Phase 1:

**From menu:**

```bash
menu launch
# Select "Take/find a note"
# Launches nb interactive interface
```text

**Quick workflows:**

```bash
# Search notes interactively
nb list --all | fzf --preview 'nb show {1}'

# Browse with gum
nb notebooks | gum choose
```text

**Theme sync:**
nb respects the current Base16 theme for syntax highlighting in `nb browse --gui`.

## Next Steps

### Phase 3: Documentation

- Update all docs to reflect new system
- Create comprehensive nb usage guide
- Document composition patterns with fzf/gum

### Phase 4: Polish & Cleanup

- Test workflows for 1-2 weeks
- Refine folder structures as needed
- Add convenience scripts if patterns emerge

## Philosophy Reinforced

From Phase 2, we learned:

1. **Multiple notebooks work** - nb unifies them seamlessly with cross-links
2. **Git-backed notes** - Each notebook is independently version controlled
3. **Public/private mix** - Learning can be public, personal stays private
4. **Composable with tools** - nb outputs clean data for fzf/gum composition
5. **Cross-referencing power** - Wiki links across notebooks maintain connections
6. **Semester-based organization** - Learning naturally organizes by time periods

---

**Conclusion:** Phase 2 successfully set up nb with three notebooks (learning, notes, ideas), each git-backed with appropriate visibility. The system supports cross-notebook linking, integrates with Phase 1 workflow tools, and follows the Unix philosophy of composability.
