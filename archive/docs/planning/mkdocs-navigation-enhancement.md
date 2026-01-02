# MkDocs Navigation Enhancement Plan

**Goal**: Transform dotfiles documentation to match MkDocs Material's navigation style and visual hierarchy

**Research Source**: MkDocs Material's own documentation site (setup/, reference/, extensions/)

## Key Findings from MkDocs Material

### Navigation Patterns

1. **Section Index Pages**: Major sections (Setup, Reference, Extensions) have clickable headers leading to overview pages
   - Example: "Setup" is bold, clickable, goes to `/setup/` which provides overview
   - Sub-items are separate pages, not sections within one page

2. **Visual Separation**: Clear spacing between major sections in sidebar
   - Setup and Extensions are visually distinct groups
   - No long scrolling lists - each topic is its own page

3. **Icons**: Font-colored icons (not emojis) in navigation for visual identification
   - Reference section uses icons extensively (one per sub-page)
   - Icons remain consistent with theme colors
   - Help with quick visual scanning

4. **Title Length**: Titles are concise, never span two lines
   - "Setting up navigation" not "How to Set Up Navigation in Your Project"
   - Action-oriented, brief

### Content Organization

1. **Hub Pages**: Main sections serve as hubs with card grids showing overview
   - Brief description of each subsection
   - Links to detailed pages
   - Quick visual scanning of what's available

2. **Separate Pages**: Each topic is its own document
   - Reference/Admonitions - separate page
   - Reference/Buttons - separate page
   - Not: Reference with sections for both

3. **Content Features Used**:
   - **Admonitions** - callout boxes for notes, warnings, tips
   - **Grids** - card layouts for overview pages
   - **Code annotations** - inline explanations in code blocks
   - **Tabbed content** - alternative options side-by-side
   - **Permanent anchors** - `¶` symbols for linking to sections

## Current Dotfiles Issues

### 1. Navigation Structure Problems

**Issue**: No section index pages

- Apps → jumps directly to Font page
- Reference → jumps directly to Platform Differences
- Sections aren't clickable hubs

**Issue**: Long scrolling pages

- `reference/platforms.md` is 100+ lines, should be split
- Could be: platforms/overview.md, platforms/packages.md, platforms/commands.md

**Issue**: Reference mixing different content types

- Platform differences
- Font documentation (5 separate pages)
- Tool references (symlinks, tasks, skills, hooks)
- Claude Code guides
- Troubleshooting
- Corporate setup

**Issue**: No icons in navigation

- Currently only repo icon configured
- Would help distinguish Apps vs Reference vs Development sections

### 2. Missing MkDocs Features

**Not using**:

- Card grids for overview pages
- Admonitions for callouts (have extension, rarely used)
- Tabbed content for alternatives
- Icons in navigation items

**Could improve**:

- Tables are functional but could use better styling
- Code blocks could have annotations
- Some pages could use better visual hierarchy

### 3. Title Length Issues

**Current titles that might be too long**:

- "Neovim AI Assistants" - fine
- "Platform Differences Reference" - could be "Platform Differences"
- "Nerd Fonts Explained" - fine
- "Font Weights and Variants" - fine
- "Go Applications" → "Go Apps" (shorter)
- "Documentation Consolidation" → "Doc Consolidation" (shorter)

## Implementation Plan

### Phase 1: Create Section Index Pages

**Goal**: Make major sections clickable with overview pages

#### Apps Section

Create `docs/apps/index.md`:

```markdown
# Apps

Personal CLI tools for enhanced workflows.

## Development Tools

<div class="grid cards" markdown>

- :fontawesome-solid-palette: **Theme Sync**
  Base16 theme management across tmux, bat, fzf, shell
  [Learn more →](theme-sync.md)

- :material-notebook: **Notes**
  Zettelkasten note-taking with zk
  [Learn more →](notes.md)

- :material-tab: **Session Manager**
  Tmux session management
  [Learn more →](sess.md)

</div>

## Utilities

<div class="grid cards" markdown>

- :fontawesome-solid-list: **Menu**
  Interactive menu system
  [Learn more →](menu.md)

- :material-toolbox: **Toolbox**
  Tool discovery CLI
  [Learn more →](toolbox.md)

- :material-backup-restore: **Backup Dirs**
  Backup directory manager
  [Learn more →](backup-dirs.md)

</div>

## Platform-Specific

<div class="grid cards" markdown>

- :fontawesome-solid-font: **Font**
  Font management for macOS
  [Learn more →](font.md)

- :material-application: **Ghostty Theme**
  Ghostty terminal theme sync
  [Learn more →](ghostty-theme.md)

</div>
```

**mkdocs.yml changes**:

```yaml
- Apps:
    - apps/index.md
    - Font: apps/font.md
    - Theme Sync: apps/theme-sync.md
    # ... rest unchanged
```

#### Architecture Section

Create `docs/architecture/index.md` (currently exists but might need hub styling)

Review current content and potentially add card grid if not present.

#### Reference Section

**Problem**: Reference is too broad, mixes many unrelated topics

**Solution**: Split into logical subsections with index page

Create `docs/reference/index.md`:

```markdown
# Reference

Quick lookup guides and technical references.

## Platform Information

<div class="grid cards" markdown>

- :material-laptop: **Platforms**
  Platform differences across macOS, WSL, Arch
  [Learn more →](platforms/index.md)

- :material-format-font: **Fonts**
  Terminal fonts and Nerd Fonts guide
  [Learn more →](fonts/index.md)

</div>

## Tools & Systems

<div class="grid cards" markdown>

- :material-link: **Symlinks Manager**
  Dotfile deployment system
  [Learn more →](symlinks.md)

- :material-run: **Task Reference**
  Available Task commands
  [Learn more →](tasks.md)

- :material-robot: **Skills System**
  Claude Code skills
  [Learn more →](skills.md)

- :material-hook: **Hooks**
  Claude Code hooks
  [Learn more →](hooks.md)

</div>

## Claude Code

<div class="grid cards" markdown>

- :material-book-open: **Usage Guide**
  Using Claude Code with dotfiles
  [Learn more →](claude-code/usage-guide.md)

- :material-monitor: **Log Monitoring**
  Research on log monitoring approaches
  [Learn more →](claude-code/log-monitoring-research.md)

</div>

## Support

<div class="grid cards" markdown>

- :material-help-circle: **Troubleshooting**
  Common issues and solutions
  [Learn more →](troubleshooting.md)

- :material-office-building: **Corporate Setup**
  Configuration for restricted environments
  [Learn more →](corporate.md)

</div>
```

#### Development Section

Create `docs/development/index.md`:

```markdown
# Development

Contributing to and testing dotfiles.

## Testing

<div class="grid cards" markdown>

- :material-docker: **VM Testing**
  Docker-based installation testing
  [Learn more →](testing.md)

</div>

## Go Development

<div class="grid cards" markdown>

- :material-language-go: **Overview**
  Go applications architecture
  [Learn more →](go-apps/overview.md)

- :material-code-braces: **Standards**
  Development standards and practices
  [Learn more →](go-apps/go-development.md)

- :material-book: **Go Quick Reference**
  Go language essentials
  [Learn more →](go-apps/go-quick-reference.md)

- :material-widgets: **Bubbletea Reference**
  TUI framework guide
  [Learn more →](go-apps/bubbletea-quick-reference.md)

</div>

## Documentation

<div class="grid cards" markdown>

- :material-format-paint: **Shell Formatting**
  ANSI formatting library
  [Learn more →](shell-formatting.md)

- :material-publish: **Publishing Docs**
  GitHub Pages deployment
  [Learn more →](publishing-docs.md)

</div>
```

#### Learnings Section

Create `docs/learnings/index.md` (already exists, enhance with cards)

Current version is 22 lines, very concise. Could add card grid for featured learnings or keep minimal as-is.

**Decision**: Keep minimal - learnings are better discovered through sidebar navigation.

### Phase 2: Split Long Documents

#### Reference/Platforms

**Current**: Single 100+ line `platforms.md` with multiple tables

**Split into**:

- `reference/platforms/index.md` - Overview with cards to sub-pages
- `reference/platforms/packages.md` - Package name differences table
- `reference/platforms/commands.md` - Command comparison tables
- `reference/platforms/tools.md` - Tool availability matrix

**Benefits**:

- Easier to navigate
- Faster page loads
- Better focused content

#### Fonts Section

**Current**: Already well organized with index page

- Keep as-is, already follows best practices

### Phase 3: Add Navigation Icons

**Goal**: Visual distinction for navigation items

#### Top-Level Sections

```yaml
nav:
  - Home: index.md
  - Apps:
      - apps/index.md
      - Font: apps/font.md
      # ...
```

**mkdocs.yml additions**:

```yaml
theme:
  icon:
    # Existing
    repo: fontawesome/brands/github
    admonition:
      # ... existing admonition icons
```

**Per-page icons** (via front matter in each document):

`docs/apps/index.md`:

```yaml
---
icon: material/apps
---
```

`docs/apps/theme-sync.md`:

```yaml
---
icon: material/palette
---
```

`docs/apps/notes.md`:

```yaml
---
icon: material/notebook
---
```

`docs/apps/sess.md`:

```yaml
---
icon: material/tab
---
```

`docs/apps/menu.md`:

```yaml
---
icon: material/menu
---
```

`docs/apps/toolbox.md`:

```yaml
---
icon: material/toolbox
---
```

`docs/apps/backup-dirs.md`:

```yaml
---
icon: material/backup-restore
---
```

`docs/apps/font.md`:

```yaml
---
icon: material/format-font
---
```

`docs/apps/ghostty-theme.md`:

```yaml
---
icon: material/application
---
```

`docs/architecture/index.md`:

```yaml
---
icon: material/city
---
```

`docs/reference/index.md`:

```yaml
---
icon: material/book-open
---
```

`docs/development/index.md`:

```yaml
---
icon: material/code-braces
---
```

`docs/learnings/index.md`:

```yaml
---
icon: material/lightbulb
---
```

`docs/changelog.md`:

```yaml
---
icon: material/timeline
---
```

#### Icon Selection Guidelines

**Use Material Design Icons** (`material/*`) as primary choice:

- Consistent style
- Large icon set
- Well-maintained

**Fontawesome** (`fontawesome/solid/*`, `fontawesome/brands/*`) for specific needs:

- Brands (GitHub, etc.)
- Specialized symbols

**Octicons** (`octicons/*`) for developer-focused icons:

- Already configured for admonitions
- GitHub-style icons

**Icon Search**: <https://squidfunk.github.io/mkdocs-material/reference/icons-emojis/#search>

### Phase 4: Enhance Content with MkDocs Features

#### Add Admonitions for Callouts

**Where to use**:

1. **Troubleshooting page** - warnings, notes, tips
2. **Installation instructions** - platform-specific requirements
3. **Architecture docs** - important concepts
4. **Learnings** - key takeaways

**Example transformation** (troubleshooting.md):

**Before**:

```markdown
## Command Not Found

**Symptom**: Tool installed but command not found

**Check PATH**:
```

**After**:

```markdown
## Command Not Found

!!! warning "Symptom"
    Tool installed but command not found

!!! tip "Check PATH"
    ```sh
    echo $PATH | tr ':' '\n'
    ```
```

#### Use Tabbed Content for Alternatives

**Where to use**:

- Platform-specific instructions
- Alternative approaches
- Different installation methods

**Example** (platforms/commands.md):

```markdown
## Package Installation

=== "macOS"

    ```bash
    brew install package-name
    ```

=== "Ubuntu"

    ```bash
    sudo apt install package-name
    ```

=== "Arch"

    ```bash
    sudo pacman -S package-name
    ```
```

#### Add Card Grids for Overview Pages

Already shown in Phase 1 index pages - use `grid cards` markdown extension.

### Phase 5: Improve Visual Hierarchy

#### Better Section Organization

**Current sections lack visual distinction** - already using `navigation.sections` feature but could optimize structure.

**mkdocs.yml optimization**:

```yaml
theme:
  features:
    # Current (keep these)
    - navigation.tabs          # Top-level tabs
    - navigation.tabs.sticky   # Sticky tabs
    - navigation.sections      # Visual grouping
    - navigation.indexes       # Section index pages
    - navigation.expand        # Auto-expand subsections
    - navigation.path          # Breadcrumbs
```

#### Consistent Page Structure

**Standard format for reference pages**:

1. **Title** (H1)
2. **Brief description** (1-2 sentences)
3. **Quick Reference** section (if applicable) - tables, commands
4. **Detailed sections** with H2/H3 hierarchy
5. **Related links** at bottom

**Standard format for index/hub pages**:

1. **Title** (H1)
2. **Brief section description** (1-2 sentences)
3. **Card grids** organized by topic
4. **Optional**: Getting started guide if needed

### Phase 6: Title Optimization

**Review and shorten where necessary**:

| Current | Proposed | Notes |
|---------|----------|-------|
| Platform Differences Reference | Platform Differences | Remove "Reference" |
| Go Applications | Go Apps | Shorter |
| Documentation Consolidation | Doc Consolidation | Shorter |
| Claude Code Hooks | Hooks | Context clear from parent |
| Claude Code: Usage Guide | Usage Guide | Context clear from parent |

### Phase 7: Update mkdocs.yml Structure

**New navigation structure**:

```yaml
nav:
  - Home: index.md

  - Apps:
      - apps/index.md
      - Theme Sync: apps/theme-sync.md
      - Notes: apps/notes.md
      - Session Manager: apps/sess.md
      - Menu: apps/menu.md
      - Toolbox: apps/toolbox.md
      - Backup Dirs: apps/backup-dirs.md
      - Font: apps/font.md
      - Ghostty Theme: apps/ghostty-theme.md

  - Architecture:
      - architecture/index.md
      - Package Management: architecture/package-management.md
      - PATH Ordering: architecture/path-ordering-strategy.md
      - Tool Composition: architecture/tool-composition.md

  - Configuration:
      - Neovim AI: configuration/neovim-ai-assistants.md

  - Reference:
      - reference/index.md
      - Platforms:
          - reference/platforms/index.md
          - Package Differences: reference/platforms/packages.md
          - Command Reference: reference/platforms/commands.md
          - Tool Availability: reference/platforms/tools.md
      - Fonts:
          - reference/fonts/index.md
          - Nerd Fonts Explained: reference/fonts/nerd-fonts-explained.md
          - Font Weights: reference/fonts/font-weights-and-variants.md
          - Terminal Fonts: reference/fonts/terminal-fonts-guide.md
          - Font Comparison: reference/fonts/font-comparison.md
      - Tools:
          - Symlinks: reference/tools/symlinks.md
          - Tasks: reference/tools/tasks.md
          - Skills: reference/tools/skills.md
          - Hooks: reference/tools/hooks.md
      - Claude Code:
          - Usage Guide: reference/claude-code/usage-guide.md
          - Log Monitoring: reference/claude-code/log-monitoring-research.md
      - Support:
          - Troubleshooting: reference/support/troubleshooting.md
          - Corporate Setup: reference/support/corporate.md

  - Development:
      - development/index.md
      - VM Testing: development/testing.md
      - Go Apps:
          - development/go-apps/overview.md
          - Standards: development/go-apps/go-development.md
          - Go Reference: development/go-apps/go-quick-reference.md
          - Bubbletea: development/go-apps/bubbletea-quick-reference.md
      - Shell Formatting: development/shell-formatting.md
      - Publishing Docs: development/publishing-docs.md

  - Learnings:
      - learnings/index.md
      - App Installation: learnings/app-installation-patterns.md
      - Arch Git Warning: learnings/arch-git-libpcre2-warning.md
      - Idempotent Installation: learnings/idempotent-installation-patterns.md
      - Testing Bootstrap: learnings/testing-bootstrap-dependencies.md
      - WSL Package Versions: learnings/wsl-ubuntu-package-versions.md
      - Package Analysis: learnings/package-version-analysis.md
      - Bash Testing: learnings/bash-testing-frameworks-guide.md
      - Script Testing: learnings/bash-script-testing.md
      - Task Printf: learnings/task-shell-printf-compatibility.md
      - Git History: learnings/git-history-rewriting.md
      - Relative Paths: learnings/relative-path-calculation.md
      - Directory Patterns: learnings/directory-pattern-matching.md
      - Cross-Platform Symlinks: learnings/cross-platform-symlink-considerations.md
      - Doc Consolidation: learnings/documentation-consolidation-principles.md
      - TUI Testing: learnings/go-tui-testing-strategies.md
      - Go Testing: learnings/go-testing-examples.md
      - TUI Ecosystem: learnings/go-tui-ecosystem-research.md
      - CLI Architecture: learnings/go-cli-architecture-analysis.md

  - Changelog:
      - changelog.md
```

**Key changes**:

1. Each major section has index page listed first
2. Reference split into logical subsections (Platforms, Fonts, Tools, Claude Code, Support)
3. Shorter navigation labels
4. Better visual grouping in sidebar

## Implementation Sequence

### Step 1: Create Index Pages (2-3 hours)

- [ ] Create `docs/apps/index.md` with card grids
- [ ] Create `docs/architecture/index.md` (or enhance existing)
- [ ] Create `docs/reference/index.md` with card grids
- [ ] Create `docs/development/index.md` with card grids
- [ ] Review `docs/learnings/index.md` (keep minimal)

### Step 2: Split Reference/Platforms (1-2 hours)

- [ ] Create `docs/reference/platforms/` directory
- [ ] Split platforms.md into:
  - [ ] index.md (overview with cards)
  - [ ] packages.md (package name table)
  - [ ] commands.md (command comparison)
  - [ ] tools.md (availability matrix)
- [ ] Update cross-references

### Step 3: Reorganize Reference Structure (1-2 hours)

- [ ] Create `docs/reference/tools/` directory
- [ ] Move symlinks.md, tasks.md, skills.md, hooks.md
- [ ] Create `docs/reference/support/` directory
- [ ] Move troubleshooting.md, corporate.md
- [ ] Update all cross-references

### Step 4: Add Icons (1 hour)

- [ ] Add front matter icon to each page
- [ ] Test icon rendering in navigation
- [ ] Adjust icon choices based on visual results

### Step 5: Update mkdocs.yml (30 minutes)

- [ ] Update navigation structure
- [ ] Test all links work
- [ ] Verify breadcrumbs display correctly

### Step 6: Enhance Content (2-3 hours)

- [ ] Add admonitions to troubleshooting
- [ ] Add tabbed content for platform differences
- [ ] Add card grids to index pages
- [ ] Review and improve visual hierarchy

### Step 7: Title Optimization (30 minutes)

- [ ] Shorten titles in navigation
- [ ] Update file content if titles change
- [ ] Test no broken links

### Step 8: Testing (1 hour)

- [ ] Build documentation locally
- [ ] Test all links work
- [ ] Verify icons display correctly
- [ ] Check mobile responsiveness
- [ ] Review overall visual hierarchy

### Step 9: Deploy (30 minutes)

- [ ] Commit changes
- [ ] Push to GitHub
- [ ] Verify GitHub Pages build
- [ ] Review live site

## Total Estimated Time: 10-14 hours

## Success Criteria

- [ ] All major sections have index pages with card grids
- [ ] Navigation includes icons for visual distinction
- [ ] No page titles span two lines
- [ ] Reference section is logically organized
- [ ] Long pages are split appropriately
- [ ] Admonitions used for important callouts
- [ ] Platform differences use tabbed content
- [ ] All links work correctly
- [ ] Visual hierarchy matches MkDocs Material style
- [ ] Mobile navigation works well

## Optional Future Enhancements

1. **Code annotations** - Add inline explanations to complex code blocks
2. **More grids** - Use generic grids for comparison layouts
3. **Status badges** - Add page status (stable, beta, deprecated)
4. **Custom CSS** - Further styling refinements in extra.css
5. **Search optimization** - Add search metadata to pages

## Notes

- Focus on navigation and structure first (Steps 1-5)
- Content enhancements (Step 6) can be gradual
- Icons should enhance, not overwhelm - use judiciously
- Keep titles action-oriented and concise
- Maintain existing features (code copy, syntax highlighting, etc.)
- Test frequently during implementation
