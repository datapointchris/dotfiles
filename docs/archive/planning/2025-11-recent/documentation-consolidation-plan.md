# Documentation Consolidation Plan

## Overview

Consolidate scattered app documentation to match the clear, concise standard set by `docs/apps/font.md` (111 lines). Remove verbose philosophy, motivation, and redundant explanations. Each app should have ONE document in `docs/apps/` that provides technical reference, not verbose workflows.

## Guiding Principles

**Documentation Philosophy** (from CLAUDE.md):
- ALWAYS write in imperative tone
- WHY over WHAT - explain decisions and trade-offs, not just commands
- Conversational paragraphs over bulleted lists - maintain context and reasoning
- Reference files instead of copying code examples
- Technical and factual, not promotional
- Add new docs to `mkdocs.yml` navigation

**Key Requirements from User**:
1. The `--help` menu for each app should be comprehensive and helpful
2. Documentation should be SHORT and CONCISE without philosophy or motivational content
3. Each app should have ONE document in `docs/apps/`
4. Remove verbose workflow guides, scattered getting-started docs
5. Focus on: clear commands, what they do, technical data (file locations, how it works)
6. Keep brief workflow examples
7. Cross-link to reference docs for deeper topics

**Font App as Model** (111 lines):
- Brief intro (2-3 lines describing what it does)
- Quick Start section (5-8 example commands)
- Commands section (concise list of commands with brief explanations)
- Data & History section (where files are stored, technical details)
- How It Works section (brief technical explanation)
- Workflow section (brief practical example)
- See Also section (cross-links)

**What to Remove**:
- ❌ Philosophy sections ("Why X Matters", "The Problem")
- ❌ Motivational content ("Stop searching, start using")
- ❌ Verbose explanations of WHY to use something
- ❌ Repetitive troubleshooting (belongs in general troubleshooting if at all)
- ❌ "Advanced Usage" that's not really advanced
- ❌ Multiple documents for one app
- ❌ Time-based estimates or scheduling suggestions

**What to Keep**:
- ✅ Clear command descriptions
- ✅ Technical details (file locations, data formats)
- ✅ Brief HOW it works explanations
- ✅ One concise workflow example
- ✅ Cross-references to related docs
- ✅ Quick Start section

## Current State Analysis

### Apps with Documentation (needs consolidation)

1. **font** - Model app ✓
   - docs/apps/font.md (111 lines) - ✅ GOOD MODEL
   - docs/reference/workflow-tools/font.md (535 lines) - 🗑️ ORPHANED, DELETE

2. **theme-sync** - 593 lines total → target ~120 lines
   - docs/workflows/themes.md (225 lines)
   - docs/reference/workflow-tools/theme-sync.md (368 lines)
   - Consolidate to: docs/apps/theme-sync.md

3. **notes** - 821 lines total → target ~140 lines
   - docs/workflows/note-taking.md (305 lines)
   - docs/reference/workflow-tools/notes.md (516 lines)
   - Consolidate to: docs/apps/notes.md

4. **sess** - 553 lines total → target ~130 lines
   - docs/workflows/sessions.md (215 lines)
   - docs/reference/workflow-tools/session.md (338 lines)
   - Consolidate to: docs/apps/sess.md

5. **menu** - 403 lines → target ~100 lines
   - docs/reference/workflow-tools/menu.md (403 lines)
   - Consolidate to: docs/apps/menu.md

6. **toolbox** - 553 lines total → target ~120 lines
   - docs/workflows/tool-discovery.md (244 lines)
   - docs/reference/workflow-tools/toolbox.md (309 lines)
   - Consolidate to: docs/apps/toolbox.md

7. **backup-dirs** - 128 lines → evaluate
   - docs/workflows/backup.md (128 lines)
   - Check if this is about backup-dirs specifically
   - Decision: Keep/consolidate/delete based on content

### Apps Without Documentation (evaluate if needed)

Simple scripts where `--help` may be sufficient:
- bashbox - Check if needs docs
- printcolors - Likely doesn't need docs (utility script)
- shelldocsparser - Check if needs docs
- tmux-colors-from-tinty - Check if needs docs
- aws-profiles (macos) - Check if needs docs
- ghostty-theme (macos) - Check if needs docs
- stitch-udacity-videos (macos) - Likely doesn't need docs (single-purpose script)

### Git Workflows Documentation

- docs/workflows/git.md (310 lines) - NOT an app, keep as workflow doc

## Execution Plan

### Phase 0: Cleanup Font Documentation

**Goal**: Complete the font documentation consolidation that was started but not finished.

**Tasks**:
1. Verify docs/apps/font.md is complete and follows the model (✓ already done)
2. Delete orphaned docs/reference/workflow-tools/font.md (535 lines)
3. Commit: `docs(font): remove orphaned reference documentation`

**Validation**:
- ✅ docs/apps/font.md exists and is comprehensive (111 lines)
- ✅ docs/reference/workflow-tools/font.md is deleted
- ✅ mkdocs.yml has `- Font: apps/font.md` under Apps section

---

### Phase 1: Theme-Sync Documentation

**Goal**: Consolidate 593 lines → ~120 lines in docs/apps/theme-sync.md

**Current State**:
- docs/workflows/themes.md (225 lines) - Verbose workflow with philosophy
- docs/reference/workflow-tools/theme-sync.md (368 lines) - Command reference

**Consolidation Strategy**:
1. Read both documents fully
2. Extract essential content:
   - Brief intro (what theme-sync does)
   - Quick Start commands
   - Command list with concise descriptions
   - How It Works (tinty integration, file locations)
   - Brief workflow example
   - Integration with ghostty-theme
   - See Also links
3. Remove:
   - "Why Theme Sync Exists" philosophy
   - Verbose workflow patterns
   - Repetitive troubleshooting
   - "Advanced Usage" section
   - Time-based theme switching examples (keep ONE brief example)

**New Document Structure** (docs/apps/theme-sync.md):
```text
# Theme Sync

Brief description (2-3 lines)

## Quick Start
[5-8 example commands]

## Commands
[Concise list of commands with brief explanations]

## How It Works
[Brief technical explanation: tinty integration, file locations]

## Integration with Ghostty
[Brief explanation of separation from ghostty-theme]

## Workflow
[ONE brief practical example]

## See Also
[Cross-links]
```

**Tasks**:
1. Create docs/apps/theme-sync.md following font.md model
2. Delete docs/workflows/themes.md
3. Delete docs/reference/workflow-tools/theme-sync.md
4. Update mkdocs.yml:
   - Add `- Theme Sync: apps/theme-sync.md` under Apps section
   - Remove from Workflows section
   - Remove from Reference > Workflow Tools section
5. Commit: `docs(theme-sync): consolidate documentation to apps/theme-sync.md`

**Validation**:
- ✅ docs/apps/theme-sync.md exists (~120 lines)
- ✅ Old docs deleted
- ✅ mkdocs.yml updated correctly
- ✅ Content is accurate and reflects current state
- ✅ No philosophy or verbose explanations

---

### Phase 2: Notes Documentation

**Goal**: Consolidate 821 lines → ~140 lines in docs/apps/notes.md

**Current State**:
- docs/workflows/note-taking.md (305 lines) - Verbose workflow
- docs/reference/workflow-tools/notes.md (516 lines) - Command reference

**Consolidation Strategy**:
1. Read both documents fully
2. Extract essential content:
   - Brief intro (wrapper around zk)
   - Quick Start commands
   - Command list with concise descriptions
   - How It Works (zk integration, notebook structure)
   - Brief workflow example
   - See Also links
3. Remove:
   - Verbose workflow patterns
   - Philosophy about note-taking
   - Repetitive examples
   - Over-explained section explanations

**New Document Structure** (docs/apps/notes.md):
```text
# Notes

Brief description (wrapper around zk)

## Quick Start
[5-8 example commands]

## Commands
[Concise list of commands]

## Notebook Structure
[Brief explanation of sections, zk integration]

## How It Works
[Brief technical explanation: zk wrapper, config location]

## Workflow
[ONE brief practical example]

## See Also
[Cross-links, link to zk documentation]
```

**Tasks**:
1. Create docs/apps/notes.md following font.md model
2. Delete docs/workflows/note-taking.md
3. Delete docs/reference/workflow-tools/notes.md
4. Update mkdocs.yml:
   - Add `- Notes: apps/notes.md` under Apps section
   - Remove from Workflows section
   - Remove from Reference > Workflow Tools section
5. Commit: `docs(notes): consolidate documentation to apps/notes.md`

**Validation**:
- ✅ docs/apps/notes.md exists (~140 lines)
- ✅ Old docs deleted
- ✅ mkdocs.yml updated correctly
- ✅ Content is accurate and reflects current state
- ✅ No verbose explanations

---

### Phase 3: Session Management (sess) Documentation

**Goal**: Consolidate 553 lines → ~130 lines in docs/apps/sess.md

**Current State**:
- docs/workflows/sessions.md (215 lines) - Verbose workflow
- docs/reference/workflow-tools/session.md (338 lines) - Command reference

**Consolidation Strategy**:
1. Read both documents fully
2. Extract essential content:
   - Brief intro (tmux session manager)
   - Quick Start commands
   - Command list with concise descriptions
   - How It Works (Go app, gum integration, config location)
   - Brief workflow example
   - See Also links
3. Remove:
   - "Why Session Management Matters" philosophy
   - Verbose workflow patterns
   - Morning setup workflow (keep as brief example)
   - Repetitive examples

**New Document Structure** (docs/apps/sess.md):
```text
# Session Manager (sess)

Brief description (tmux session manager)

## Quick Start
[5-8 example commands]

## Commands
[Concise list of commands]

## How It Works
[Brief technical explanation: Go app, gum integration, config location, session types]

## Configuration
[Brief note about default sessions config]

## Workflow
[ONE brief practical example]

## See Also
[Cross-links to tmux docs]
```

**Tasks**:
1. Create docs/apps/sess.md following font.md model
2. Delete docs/workflows/sessions.md
3. Delete docs/reference/workflow-tools/session.md
4. Update mkdocs.yml:
   - Add `- Session Manager: apps/sess.md` under Apps section
   - Remove from Workflows section
   - Remove from Reference > Workflow Tools section
5. Commit: `docs(sess): consolidate documentation to apps/sess.md`

**Validation**:
- ✅ docs/apps/sess.md exists (~130 lines)
- ✅ Old docs deleted
- ✅ mkdocs.yml updated correctly
- ✅ Content is accurate and reflects current state
- ✅ No philosophy sections

---

### Phase 4: Menu Documentation

**Goal**: Consolidate 403 lines → ~100 lines in docs/apps/menu.md

**Current State**:
- docs/reference/workflow-tools/menu.md (403 lines) - Command reference

**Consolidation Strategy**:
1. Read document fully
2. Extract essential content:
   - Brief intro (workflow tool launcher)
   - Quick Start
   - How It Works (integration with other tools)
   - Brief structure explanation
   - See Also links
3. Remove:
   - Verbose explanations
   - Over-detailed menu structure
   - Keep it simple - this is a launcher

**New Document Structure** (docs/apps/menu.md):
```text
# Menu

Brief description (workflow tool launcher)

## Quick Start
[Basic usage]

## How It Works
[Brief explanation of menu system, integration with other tools]

## Available Tools
[Brief list of what's available through menu]

## See Also
[Cross-links to individual tool docs]
```

**Tasks**:
1. Create docs/apps/menu.md following font.md model
2. Delete docs/reference/workflow-tools/menu.md
3. Update mkdocs.yml:
   - Add `- Menu: apps/menu.md` under Apps section
   - Remove from Reference > Workflow Tools section
4. Commit: `docs(menu): consolidate documentation to apps/menu.md`

**Validation**:
- ✅ docs/apps/menu.md exists (~100 lines)
- ✅ Old docs deleted
- ✅ mkdocs.yml updated correctly
- ✅ Content is accurate and reflects current state
- ✅ Simple and concise

---

### Phase 5: Toolbox Documentation

**Goal**: Consolidate 553 lines → ~120 lines in docs/apps/toolbox.md

**Current State**:
- docs/workflows/tool-discovery.md (244 lines) - Verbose workflow
- docs/reference/workflow-tools/toolbox.md (309 lines) - Command reference

**Consolidation Strategy**:
1. Read both documents fully
2. Extract essential content:
   - Brief intro (tool discovery system)
   - Quick Start commands
   - Command list with concise descriptions
   - How It Works (registry.yml, Go app structure)
   - Brief workflow example
   - See Also links
3. Remove:
   - Verbose workflow patterns
   - Over-explained discovery process
   - Philosophy about tool discovery

**New Document Structure** (docs/apps/toolbox.md):
```text
# Toolbox

Brief description (tool discovery system)

## Quick Start
[5-8 example commands]

## Commands
[Concise list of commands]

## How It Works
[Brief technical explanation: registry.yml, Go app, data location]

## Registry
[Brief explanation of docs/tools/registry.yml structure]

## Workflow
[ONE brief practical example]

## See Also
[Cross-links]
```

**Tasks**:
1. Create docs/apps/toolbox.md following font.md model
2. Delete docs/workflows/tool-discovery.md
3. Delete docs/reference/workflow-tools/toolbox.md
4. Update mkdocs.yml:
   - Add `- Toolbox: apps/toolbox.md` under Apps section
   - Remove from Workflows section
   - Remove from Reference > Workflow Tools section
5. Commit: `docs(toolbox): consolidate documentation to apps/toolbox.md`

**Validation**:
- ✅ docs/apps/toolbox.md exists (~120 lines)
- ✅ Old docs deleted
- ✅ mkdocs.yml updated correctly
- ✅ Content is accurate and reflects current state
- ✅ No verbose explanations

---

### Phase 6: Backup Documentation Evaluation

**Goal**: Evaluate docs/workflows/backup.md (128 lines)

**Tasks**:
1. Read docs/workflows/backup.md
2. Determine if this is about the backup-dirs app specifically
3. Check backup-dirs --help menu

**Decision Tree**:
- If it's about backup-dirs app:
  - Consolidate to docs/apps/backup-dirs.md (~80 lines)
  - Remove verbose workflow content
  - Focus on what the app does
- If it's about general backup workflow:
  - Keep in docs/workflows/backup.md but trim to essentials
  - Or move to docs/reference/ if it's more reference than workflow

**Tasks After Decision**:
1. Create/update appropriate documentation
2. Delete/move old documentation
3. Update mkdocs.yml accordingly
4. Commit with appropriate message

---

### Phase 7: Evaluate Undocumented Apps

**Goal**: Determine if simple scripts need documentation

For each app, check:
1. The --help menu quality
2. Complexity of the script
3. Whether it's user-facing or internal

**Apps to Evaluate**:

1. **bashbox** (10KB script)
   - Check --help
   - Determine if documentation needed
   - Decision: Document or note that --help is sufficient

2. **printcolors** (1.1KB script)
   - Check --help
   - Likely doesn't need docs (simple utility)
   - Decision: No docs needed, --help sufficient

3. **shelldocsparser** (6KB script)
   - Check --help
   - Determine if documentation needed
   - Decision: Document or note that --help is sufficient

4. **tmux-colors-from-tinty** (3KB script)
   - Check --help
   - Likely internal utility, may not need docs
   - Decision: Document if user-facing, skip if internal

5. **aws-profiles** (2.7KB script, macOS only)
   - Check --help
   - macOS-specific tool
   - Decision: Document if complex, skip if --help sufficient

6. **ghostty-theme** (9.5KB script, macOS only)
   - Check --help
   - Themes are important to user
   - Decision: Likely needs brief documentation

7. **stitch-udacity-videos** (6.4KB script, macOS only)
   - Check --help
   - Single-purpose tool, likely doesn't need docs
   - Decision: No docs needed

**Tasks**:
1. Check each app's --help menu
2. Make documentation decision for each
3. Create brief docs (~50-80 lines) if needed
4. Update mkdocs.yml for any new docs
5. Commit: `docs(apps): add documentation for [app]` or `docs: evaluate undocumented apps`

---

### Phase 8: Final Cleanup

**Goal**: Ensure mkdocs.yml is clean and all documentation is accurate

**Tasks**:
1. Review mkdocs.yml navigation structure
2. Ensure all apps are in the Apps section
3. Verify Workflows section doesn't have app docs
4. Verify Reference > Workflow Tools section is removed or repurposed
5. Check for any broken links in documentation
6. Verify all See Also cross-references are valid
7. Build docs locally and test navigation
8. Commit: `docs: finalize navigation and cleanup mkdocs.yml`

**Final mkdocs.yml Apps Section** (target):
```yaml
- Apps:
    - Font: apps/font.md
    - Theme Sync: apps/theme-sync.md
    - Notes: apps/notes.md
    - Session Manager: apps/sess.md
    - Menu: apps/menu.md
    - Toolbox: apps/toolbox.md
    # Add others as needed based on Phase 7 decisions
```

**Workflows Section** (after cleanup):
```yaml
- Workflows:
    - Git Operations: workflows/git.md
    # Keep only true workflow docs, not app documentation
```

**Reference Section** (after cleanup):
```yaml
- Reference:
    # Remove "Workflow Tools" subsection entirely
    # Or repurpose for other reference material
```

---

## Success Criteria

After completion, the documentation should meet these criteria:

1. **Structure**:
   - ✅ Each app has ONE document in docs/apps/
   - ✅ No scattered documentation across workflows/ and reference/
   - ✅ mkdocs.yml Apps section contains all app documentation

2. **Content Quality**:
   - ✅ Each doc follows font.md model (~80-150 lines)
   - ✅ No philosophy or motivational content
   - ✅ No verbose "Why X Matters" sections
   - ✅ Clear command descriptions
   - ✅ Technical details (file locations, how it works)
   - ✅ Brief workflow examples
   - ✅ Cross-references to related docs

3. **Accuracy**:
   - ✅ All information reflects current state of the app
   - ✅ All file paths are correct
   - ✅ All commands are accurate
   - ✅ All links work

4. **Completeness**:
   - ✅ All major apps have documentation
   - ✅ Simple scripts evaluated for documentation needs
   - ✅ Decision documented for apps without docs
   - ✅ mkdocs.yml navigation is clean and logical

5. **Git History**:
   - ✅ Each phase committed separately
   - ✅ Commit messages are clear and descriptive
   - ✅ Each commit is atomic (one app at a time)

---

## Execution Notes

- Work **slowly and methodically**
- Complete each phase fully before moving to the next
- Commit after each app is done
- No time limit, no effort limit
- Focus on quality and accuracy
- When in doubt, favor brevity over verbosity
- Keep the font.md model in mind for every app
- Remember: The --help menu is comprehensive, docs should be concise reference

---

## Appendix: Font.md Reference Structure

For quick reference while consolidating other apps:

```markdown
# App Name

Brief description (2-3 lines about what it does and why it exists)

## Quick Start

```bash
app command1          # Brief description
app command2 "arg"    # Brief description
app command3          # Brief description
```

## Commands

### Category 1

- `app cmd1` - Brief description
- `app cmd2 <arg>` - Brief description

### Category 2

- `app cmd3` - Brief description

Additional explanation if needed (1-2 paragraphs max)

## Data & Storage

Where files are stored, data format, any important technical details

## How It Works

Brief technical explanation of the system (1-3 paragraphs)

## Workflow

Practical example showing common usage pattern (keep brief)

```bash
app cmd1
# Brief explanation
app cmd2
```

## See Also

- [Related Doc](../path/to/doc.md) - Brief description
```

---

## Timeline Estimate

**Note**: This is for planning purposes only. Actual execution will be thorough and careful, taking as much time as needed.

- Phase 0: Font cleanup - ~10 minutes
- Phase 1: Theme-sync - ~45 minutes
- Phase 2: Notes - ~45 minutes
- Phase 3: Sess - ~45 minutes
- Phase 4: Menu - ~30 minutes
- Phase 5: Toolbox - ~45 minutes
- Phase 6: Backup evaluation - ~20 minutes
- Phase 7: Undocumented apps - ~45 minutes
- Phase 8: Final cleanup - ~30 minutes

**Total estimated time**: ~4-5 hours of focused work

**Actual time**: Take as long as needed to do it right

---

## Next Step

Begin with **Phase 0: Cleanup Font Documentation** by deleting the orphaned reference file.
