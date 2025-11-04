# Documentation Reorganization Plan

**Date**: 2025-11-04
**Goal**: Transform docs into a wiki-style technical documentation site that enables returning after a year and being productive in a day

## Inspiration

CodeCompanion.nvim documentation structure:

- Task-oriented hierarchy (concepts → setup → usage → customization)
- Collapsible sections in navigation
- Linear onboarding for beginners
- Deep customization sections for advanced users
- Modular organization

## Documentation Purpose

The documentation serves multiple audiences and use cases:

1. **New User (Day 1)**: Quick start guide to get dotfiles installed and working
2. **Returning User (After 1 Year)**: Refresh on how everything works, what's changed
3. **Customizer**: Deep dive into configuration, theming, tool management
4. **Contributor**: Understanding architecture, testing, development workflow
5. **Troubleshooter**: Quick reference for common issues and platform differences

## Proposed Structure

### 1. Home (index.md)

**Purpose**: 30-second overview of what these dotfiles are and why they exist

**Content**:

- What are these dotfiles?
- Key features (31 tools, theme sync, cross-platform)
- Quick navigation to common tasks
- Visual diagram of architecture

**Files**: New index.md (consolidate README.md content)

---

### 2. Getting Started

**Purpose**: Linear onboarding - install and start using in 15 minutes

**Pages**:

1. **Quick Start** (quickstart.md)
   - Prerequisites
   - One-command installation
   - First steps after install
   - Verify everything works

2. **Installation Guide** (installation/index.md)
   - Platform-specific instructions
   - macOS installation
   - WSL Ubuntu installation
   - Arch Linux installation
   - Troubleshooting install issues

3. **First Configuration** (first-config.md)
   - Setting your Git identity
   - Choosing a theme
   - Exploring installed tools
   - Next steps

**Files**:

- New quickstart.md
- Move setup.md → installation/index.md
- Enhance with platform-specific sections
- New first-config.md

---

### 3. Core Concepts

**Purpose**: Understand HOW and WHY everything works

**Pages**:

1. **Architecture Overview** (architecture/index.md)
   - How dotfiles are organized (common/ + platform/)
   - Symlink system
   - Taskfile automation
   - Version managers (nvm, uv)

2. **Package Management Philosophy** (architecture/package-management.md)
   - Why uv for Python, nvm for Node
   - System packages vs language packages
   - Cross-platform consistency

3. **Tool Discovery System** (architecture/tool-discovery.md)
   - Why we built the `tools` command
   - How the registry works
   - Discovery over tracking philosophy

4. **Theme System** (architecture/themes.md)
   - tinty and Base16 themes
   - Parallel systems (ghostty-theme + theme-sync)
   - How themes synchronize across apps

**Files**:

- New architecture/index.md (consolidate dotfiles-management-analysis.md)
- New architecture/package-management.md (from MASTER_PLAN)
- New architecture/tool-discovery.md (from phase_5_complete.md)
- New architecture/themes.md (from phase_4_complete.md + THEME_SYNC_STRATEGY.md)

---

### 4. Configuration

**Purpose**: Customize and extend the dotfiles

**Pages**:

1. **Themes & Colors** (configuration/themes.md)
   - Available Base16 themes
   - Switching themes
   - Creating custom themes
   - Per-application theme settings

2. **Tools & CLI** (configuration/tools.md)
   - Using the `tools` command
   - Tool registry structure
   - Adding new tools
   - Tool categories

3. **Shell Configuration** (configuration/shell.md)
   - Zsh setup and plugins
   - Custom aliases and functions
   - PATH management
   - Platform-specific configs

4. **Neovim** (configuration/neovim.md)
   - LSP setup
   - Colorscheme manager
   - Key plugins and workflows
   - AI integration (CodeCompanion)

5. **Terminal & Workflow** (configuration/workflow.md)
   - Ghostty configuration
   - Aerospace + Tmux + Neovim workflow
   - Tmux setup and keybindings

**Files**:

- Move neovim/* → configuration/neovim/ (consolidate)
- Move terminal/* → configuration/ (merge into workflow.md)
- Move workflow/* → configuration/workflow.md
- New configuration/themes.md
- New configuration/tools.md
- Consolidate ai.md into configuration/neovim.md

---

### 5. Development

**Purpose**: Contributing, testing, and understanding the development process

**Pages**:

1. **Development Overview** (development/index.md)
   - Project phases (1-6 complete)
   - Development philosophy
   - How to contribute

2. **Testing Guide** (development/testing.md)
   - VM testing framework
   - Testing on Ubuntu (multipass)
   - Testing on Arch (UTM/QEMU)
   - Testing on macOS (fresh user)
   - CI/CD (future)

3. **Project Phases** (development/phases.md)
   - Phase 1: Package Management ✅
   - Phase 2: Tool Registry ✅
   - Phase 3: Installation Automation ✅
   - Phase 4: Theme Synchronization ✅
   - Phase 5: Tool Discovery ✅
   - Phase 6: Cross-Platform Expansion ✅
   - Phase 7: CI/CD (planned)

4. **Master Plan** (development/master-plan.md)
   - Full MASTER_PLAN document
   - Project goals and philosophy
   - Implementation timeline
   - Decisions made

**Files**:

- New development/index.md
- Move vm_testing_guide.md → development/testing.md
- New development/phases.md (consolidate all phase_N_complete.md)
- Move MASTER_PLAN.md → development/master-plan.md

---

### 6. Reference

**Purpose**: Quick lookup for specific information

**Pages**:

1. **Platform Differences** (reference/platforms.md)
   - Package name mappings
   - Binary name differences
   - Platform-specific quirks
   - Cross-platform compatibility

2. **Tool Registry** (reference/tools.md)
   - All 31 tools documented
   - Categories and tags
   - Installation methods
   - Links to official docs

3. **Taskfile Reference** (reference/taskfile.md)
   - All available tasks
   - Task categories
   - Platform-specific tasks
   - Common task workflows

4. **Troubleshooting** (reference/troubleshooting.md)
   - Common issues by platform
   - Installation problems
   - Tool not found errors
   - Symlink issues
   - Theme problems

5. **Corporate Setup** (reference/corporate.md)
   - Work environment constraints
   - LSP installation on restricted systems
   - Workarounds for limited access

**Files**:

- Move platform_differences.md → reference/platforms.md
- Move TOOL_LIST.md → reference/tools.md (enhance with registry.yml data)
- New reference/taskfile.md
- Move troubleshooting.md → reference/troubleshooting.md
- Move corporate.md → reference/corporate.md

---

### 7. Changelog

**Purpose**: Historical record of all changes

**Structure**:

- Keep changelog/ directory as-is
- Keep detailed history in individual files
- Main changelog.md as index

**Files**: No changes, keep as-is

---

## Files to Remove/Consolidate

### Remove

- `examples/` directory (mkdocs demo content, not needed)
- `VM_TESTING_PLAN.md` (superseded by vm_testing_guide.md)
- `environment-setup.md` (merge into setup → installation)
- `nvim-migration.md` (historical, move to changelog or remove)
- `lsp.md` (standalone, merge into neovim section)

### Consolidate

- All `PHASE_N_COMPLETE.md` → `development/phases.md`
- All neovim docs → single section
- `THEME_SYNC_STRATEGY.md` + `phase_4_complete.md` → `architecture/themes.md`
- `dotfiles-management-analysis.md` → `architecture/index.md`

## Navigation Structure (mkdocs.yml)

```yaml
nav:
  - Home: index.md

  - Getting Started:
      - Quick Start: getting-started/quickstart.md
      - Installation: getting-started/installation.md
      - First Configuration: getting-started/first-config.md

  - Core Concepts:
      - Architecture: architecture/index.md
      - Package Management: architecture/package-management.md
      - Tool Discovery: architecture/tool-discovery.md
      - Theme System: architecture/themes.md

  - Configuration:
      - Themes & Colors: configuration/themes.md
      - Tools & CLI: configuration/tools.md
      - Shell: configuration/shell.md
      - Neovim: configuration/neovim.md
      - Workflow: configuration/workflow.md

  - Development:
      - Overview: development/index.md
      - Testing Guide: development/testing.md
      - Project Phases: development/phases.md
      - Master Plan: development/master-plan.md

  - Reference:
      - Platform Differences: reference/platforms.md
      - Tool Registry: reference/tools.md
      - Taskfile Reference: reference/taskfile.md
      - Troubleshooting: reference/troubleshooting.md
      - Corporate Setup: reference/corporate.md

  - Changelog:
      - Overview: changelog.md
      - 2025-11-04: changelog/2025-11-04.md
      - 2025-11-02: changelog/2025-11-02.md
```

## Visual Enhancements

### mkdocs-material Features to Add

1. **Navigation**:
   - Keep navigation.tabs (top-level sections)
   - Keep navigation.sections (collapsible groups)
   - Add navigation.path (breadcrumb trail)
   - Consider navigation.prune (reduce page load)

2. **Content**:
   - Add content.tabs (tabbed code examples)
   - Add content.code.annotate (annotated code blocks)
   - Keep content.code.copy

3. **Search**:
   - Already have search plugin
   - Consider search.suggest
   - Consider search.highlight

4. **Theme**:
   - Current slate scheme is good
   - Consider adding palette toggle (light/dark)
   - Add custom CSS for spacing (CodeCompanion-style)

### Custom CSS Enhancements

Create `stylesheets/extra.css`:

- Increase line height for readability
- Add breathing room to navigation
- Enhance code block styling
- Add custom admonition styles

## Implementation Order

1. **Phase 1**: Create new directory structure
   - getting-started/
   - architecture/
   - configuration/
   - development/
   - reference/

2. **Phase 2**: Create new consolidated files
   - index.md (home)
   - getting-started/quickstart.md
   - architecture/index.md
   - development/phases.md

3. **Phase 3**: Move and enhance existing files
   - Move files to new locations
   - Update internal links
   - Consolidate duplicate content

4. **Phase 4**: Update mkdocs.yml
   - New navigation structure
   - Enhanced features
   - Updated theme settings

5. **Phase 5**: Test and refine
   - Build site locally
   - Check all links
   - Verify navigation
   - Adjust spacing and layout

## Success Criteria

✅ Can find "Quick Start" in < 5 seconds
✅ Can understand architecture in < 15 minutes
✅ Can customize themes in < 10 minutes
✅ Can troubleshoot issues in < 5 minutes
✅ Can contribute/test in < 20 minutes
✅ Can navigate without friction
✅ Returning after 1 year: productive in 1 day

## Notes

- Keep changelog/ directory untouched (full history)
- Remove marketing language, keep technical
- Focus on "why" not just "what"
- Cross-reference related topics
- Use admonitions for important notes
- Code examples for all commands
- Screenshots where helpful (workflow diagrams)
