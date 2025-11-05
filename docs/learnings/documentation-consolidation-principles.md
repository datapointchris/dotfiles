# Documentation Consolidation Principles

**Context**: CLAUDE.md refactor (2025-11-05) - reduced from 350 to 150 lines while improving clarity and focus

## The Problem

CLAUDE.md had grown to 350 lines with multiple issues:

- Outdated sections referencing completed work from months ago
- Verbose explanations that duplicated what's in the actual docs
- Marketing-style language inappropriate for personal tooling
- Mixing architectural decisions with transient project status
- Too many detailed subsections that felt like they were written for an audience

The file was trying to do too much - be a user guide, a comprehensive reference, and project status tracker all at once.

## The Solution

Consolidated to 150 lines by applying these principles:

**Focus on what Claude needs to know**: Critical rules, architectural decisions, and project-specific context. Remove verbose explanations of things documented elsewhere.

**Current project reference, not history**: Mention key systems based on actual directory structure and recent git commits. Remove "Recent Work" and "Current Goals" sections that quickly become stale.

**Concise over comprehensive**: Replace 80-line documentation philosophy with 20 lines capturing core principles. Users can explore tools via commands/docs instead of reading detailed descriptions.

**Personal tooling voice**: Remove marketing language, "Primary Audiences" lists, and feature-style descriptions. This is for me, not for marketing to others.

**Consolidate related sections**: Merge "Coding Preferences" into "Problem Solving Philosophy". Combine multiple Git protocol subsections into unified rules.

## Key Learnings

- CLAUDE.md is for Claude Code to work effectively, not a user manual
- Reference other documentation instead of duplicating content
- Keep project overview current by checking git history and directory structure
- Remove sections that change frequently (goals, recent work, communication style)
- Consolidate verbose multi-subsection explanations into focused paragraphs
- When in doubt, delete - users can explore via tools/docs/code

## Before/After Example

**Before** (40+ lines):

```markdown
### Documentation Purpose

The dotfiles documentation serves as a comprehensive wiki-style technical resource designed for multiple audiences and use cases:

**Primary Audiences**:
1. New User (Day 1): Quick start guide...
2. Returning User (After 1 Year): Refresh understanding...
[...continues with extensive subsections...]
```

**After** (20 lines):

```markdown
## Documentation Philosophy

Documentation in this repository serves as a technical reference for future me (6+ months later) and follows these principles:

**Writing Guidelines**:
- WHY over WHAT - explain decisions and trade-offs, not just commands
- Conversational paragraphs over bulleted lists - maintain context and reasoning
[...focused bullet points...]
```

## Application to Other Documentation

These principles apply broadly:

- Architecture docs should explain WHY, not just WHAT
- Reference docs should be concise with pointers to code/tools
- Learnings stay focused on extracted wisdom (30-50 lines)
- Remove content that duplicates what code/tools already show
- Personal tooling doesn't need marketing language or audience analysis

## Related

- `docs/` - Full documentation organized by purpose
- `.claude/skills/symlinks-developer/SKILL.md` - Example of focused skill documentation
- `mkdocs.yml` - Documentation navigation structure
