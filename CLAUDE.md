# Claude AI Assistant - Neovim Development Context

## About Me

I'm Chris, a software engineer who uses a dotfiles-based development environment across macOS, WSL, and Ubuntu. I prefer clean, maintainable code and enjoy optimizing developer experience.

## Development Environment

- **Editor**: Neovim 0.11+ with native LSP configuration
- **Shell**: Zsh with custom prompt and enhanced CLI tools
- **Platforms**: macOS (primary), WSL, Ubuntu
- **Terminal**: iTerm2 on macOS, various on Linux
- **AI Coding**: CodeCompanion.nvim with Claude 3.5 Sonnet

## Current Project Context

Working on a cross-platform dotfiles repository with shared configurations and platform-specific overrides. Recently migrated from Mason-based LSP to Neovim 0.11 native LSP and enhanced CodeCompanion setup.

### Key Files

- `symlinks` - Core symlink management tool
- `common/` - Common dotfiles between all operating systems
- `macos/` - MacOS specific dotfiles and configuration
- `wsl/` - WSL using Ubuntu specific dotfiles for use on a slightly restricted work computer
- `docs/` - documentation for the dotfiles, stored in mkdocs style
- Platform-specific Git configs with different editors/credentials

### Symlink Management

This dotfiles repository uses a symlink system to deploy configuration files from the repo to their expected locations in the home directory. When files are added or removed from the dotfiles, the symlinks must be updated.

**Critical Rule**: After adding or removing any files in the dotfiles repository, you MUST run the symlink update command:

- macOS: `./symlinks relink macos`
- WSL: `./symlinks relink wsl`

**Common Symptoms of Outdated Symlinks**:

- "module not found" errors in Neovim after creating new files in `lua/` directories
- Configuration files not being picked up by applications
- Files existing in the dotfiles repo but not accessible in their expected locations

Always check symlinks first when encountering file-related issues after making structural changes to the repository.

## Coding Preferences

- **Architecture**: DRY principles, intelligent symlink management
- **LSP**: Native Neovim LSP over plugin ecosystems when possible
- **AI Assistance**: Prefer comprehensive explanations with implementation
- **Documentation**: Clear README files, inline comments for complex logic
- **Testing**: Pre-commit hooks, shell validation, configuration testing
- **Problem-Solving Approach**: Always err on the side of thinking through issues rather than adding extra code. When debugging, analyze what existing code does and test minimal changes first instead of adding complex filtering or workarounds

## Documentation Philosophy

When creating or updating documentation:

### Audience

- **Primary**: Future me (6+ months later) trying to remember why decisions were made
- **Secondary**: Technical developers familiar with the technology stack
- **Context**: Always within the broader dotfiles project ecosystem

### Content Focus

- **WHY over WHAT**: Architectural decisions, trade-offs
- **Context over Code**: How components fit together, not implementation details
- **Stability over Examples**: Principles that don't change vs code that does

### Documentation Structure

Avoid creating too many bulleted lists. A bulleted list loses a lot of information that long form sentences and explanations can maintain. Prefer to always talk in a person to person manner as if having a conversation with another developer on a pull request that was created to explain the code and how the project works.

**Documentation Guidelines:**

- Focus on **concise architectural explanations** rather than verbose step-by-step processes
- Emphasize **how systems work together** and **why they are designed that way**
- Use **paragraphs of explanation** as the primary structure for conveying context and reasoning
- Include **selective bulleted lists** for overviews only, not as the main documentation format
- Keep **code snippets minimal** - include command names or key concepts, not full implementations
- Maintain a **conversational tone** as if explaining technical decisions to another developer

Avoid documentation that is primarily bulleted lists or verbose procedural steps. Instead, focus on architectural understanding and the reasoning behind design decisions.

### Writing Style

- **Technical, not promotional**: State facts and reasoning, not "features"
- **Context-aware**: Reference other dotfiles components and decisions
- **Decision-focused**: Document the "why" behind choices made
- **Maintenance-oriented**: Help future maintenance and debugging

### Avoid

- ❌ Marketing language ("amazing", "powerful", "best")
- ❌ Step-by-step tutorials (they go stale)
- ❌ Extensive code examples (reference files instead)
- ❌ Feature lists without context or reasoning

## Recent Work

1. Completed migration from Mason LSP to native vim.lsp.config()
2. Implemented 20+ language servers (Python, JavaScript, Lua, etc.)
3. Enhanced CodeCompanion with memory system and VSCode-like experience
4. Integrated Claude 3.5 Sonnet adapter with project context awareness

## Communication Style

- Like to understand the "why" behind architectural decisions
- Prefer seeing the code changes implemented rather than just described
- Value cross-platform compatibility considerations

## Changelog Requirements

**IMPORTANT**: Automatically maintain changelog entries for all changes made to this dotfiles repository.

### Changelog Structure

1. **Summary File**: `docs/changelog.md`
   - High-level overview of changes
   - Entries organized by date in YYYY-MM-DD format
   - Each entry has an `id` matching the date: `## YYYY-MM-DD {#YYYY-MM-DD}`
   - Brief title and description of what changed
   - List of key changes and files modified
   - Link to detailed changelog

2. **Detailed File**: `docs/changelog/YYYY-MM-DD.md`
   - In-depth analysis of changes from our conversation
   - Multiple unrelated changes can be in the same file (one file per day)
   - Each change section has its own heading with anchor: `## Title {#anchor-name}`

### Required Content in Detailed Changelog

For each change, include:

1. **Problem Statement**: What was wrong or what needed to be changed
2. **Solution Overview**: High-level approach taken
3. **Errors Encountered**: All errors hit during implementation
   - Error messages (exact text)
   - Root cause analysis
   - The fix that was applied
   - Why that fix was chosen
4. **Testing Methodology**:
   - Scripts used to test changes
   - Why those specific testing approaches were chosen
   - What each test validated
5. **Files Modified**: Complete list with brief description of changes
6. **Final Resolution**: Summary of working state after all fixes
7. **Learnings**: Key insights, gotchas, and wisdom for future reference

### Changelog Entry Format Example

**Summary (docs/changelog.md):**

```markdown
## 2025-11-02 {#2025-11-02}

### Feature/Fix Title

Brief description of what changed and why.

**Key Changes:**
- Bullet point of major change
- Another major change

**Files Changed:**
- Created/Modified: path/to/file

See [detailed changelog](changelog/2025-11-02.md#anchor-name) for full details.
```

**Detailed (docs/changelog/YYYY-MM-DD.md):**

```markdown
## Feature/Fix Title {#anchor-name}

### Problem Statement
What was broken or needed...

### Solution Overview
How we approached it...

### Errors Encountered and Solutions

#### Error 1: Title
**Error Message:** ```exact error text```
**Root Cause:** Why it happened
**Fix:** What we changed
**Why This Fix:** Reasoning behind the solution

[Continue for all errors...]

### Testing Methodology
Scripts used, why chosen, what validated...

### Files Modified
List with descriptions...

### Final Resolution
Summary of working state...

### Learnings
Key insights and gotchas...
```

### When to Create Changelog Entries

Create changelog entries whenever:

- Adding new features or tools
- Fixing bugs or configuration issues
- Refactoring code or reorganizing files
- Updating plugins or dependencies
- Making architectural changes
- Any change that would be useful to remember or learn from

### Changelog Workflow

1. At the end of any work session where dotfiles were modified:
   - Update `docs/changelog.md` with high-level summary
   - Create or append to `docs/changelog/YYYY-MM-DD.md` with detailed analysis
2. Use insights from our conversation to document the journey, not just the destination
3. Be thorough with error documentation - future debugging will thank you
4. Include testing scripts and methodologies used
5. Always add a Learnings section with actionable insights

## Current Goals

- Optimize CodeCompanion workflow for seamless AI-assisted development
- Maintain clean, conflict-free native LSP configuration
- Document setup for future maintenance and sharing
- Create efficient development workflows across all platforms
- **Maintain comprehensive changelogs for all dotfiles changes**
