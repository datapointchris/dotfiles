# Notes System Setup

## Overview

Single zk notebook with selective git tracking:

- **Location**: `~/Documents/notes` (iCloud synced)
- **Symlink**: `~/notes` → `~/Documents/notes` (convenience)
- **Git tracking**: `devnotes/` and `learning/` only
- **Personal content**: iCloud backup only

## Setup Steps

### 1. Create Symlink

```bash
ln -s ~/Documents/notes ~/notes
```

### 2. Initialize Git

```bash
cd ~/Documents/notes

# Initialize git
git init

# Create gitignore
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

# Initial commit
git add .
git commit -m "feat: initialize notes repository"

# Add remote
git remote add origin git@github.com:yourusername/notes.git
git push -u origin main
```

### 3. Create Directory Structure

```bash
cd ~/notes
mkdir -p journal learning devnotes ideas projects dreams .zk/templates
```

### 4. Create Templates

Place these in `~/notes/.zk/templates/`:

#### journal.md

```markdown
---
date: {{date}}
---

# {{title}}

## Entry


## Tags

#journal
```

#### learning.md

```markdown
---
date: {{date}}
topic:
---

# {{title}}

## Overview


## Key Concepts


## Resources


#learning
```

#### devnote.md

```markdown
---
date: {{date}}
tags: dev
---

# {{title}}

## Problem


## Solution


#devnotes
```

#### idea.md

```markdown
---
date: {{date}}
status: idea
---

# {{title}}

## Description


## Next Steps


#ideas
```

#### project.md

```markdown
---
title: {{title}}
status: planning
started: {{date}}
---

# {{title}}

## Overview


## Tasks

- [ ]


#projects
```

#### dream.md

```markdown
---
date: {{date}}
---

# Dream - {{date}}

## Description


#dreams
```

#### default.md

```markdown
---
date: {{date}}
---

# {{title}}


```

## Usage

### Interactive Menu

```bash
notes                    # Auto-discovers sections, shows gum menu
notes journal            # Create journal entry directly
```

### Using zk Directly

```bash
zk journal "My thoughts"
zk learn "Rust lifetimes"
zk devnote "API design"
zk idea "Cool project"

zk recent                # List 20 most recent
zk today                 # Today's notes
zk last                  # Edit last modified
```

### In Neovim

- `<leader>zn` - New note
- `<leader>zo` - Browse notes
- `<leader>zf` - Search notes
- `<leader>zt` - Browse tags

## What Gets Tracked

**Tracked (git → remote):**

- `devnotes/` - Work notes, shareable
- `learning/` - Study notes, shareable
- `.zk/` - Config and templates

**Not tracked (iCloud only):**

- `journal/` - Personal
- `ideas/` - Personal
- `projects/` - Personal
- `dreams/` - Personal

## At Work

```bash
git clone git@github.com:you/notes.git ~/notes

# Result:
# - devnotes/ (full content)
# - learning/ (full content)
# - Empty personal directories
# - All wikilinks from devnotes → learning work
# - Links to personal notes show as dead links (expected)

# Add work notes
zk devnote "Production deploy"
git add devnotes/
git commit -m "docs: add deployment notes"
git push
```

## Future: URL Capture

Create `~/bin/capture-url`:

```bash
#!/usr/bin/env bash
url=$(pbpaste)
title=$(gum input --placeholder "Title")
section=$(gum choose "ideas" "devnotes" "learning")

cat > "/tmp/note-content.md" << EOF
# $title

URL: $url

## Notes

EOF

zk "$section" "$title" < /tmp/note-content.md
```

Bind in Aerospace config.
