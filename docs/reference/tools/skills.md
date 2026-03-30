# Skills System (Deprecated)

!!! warning "Deprecated"
    This page describes a per-repository skills system that was designed but never implemented. The `.claude/skill-rules.json`, `.claude/skills/` directory, and `SKILL.md` files referenced in earlier versions of this page never existed in the dotfiles repo.

## What Happened

The original plan was to build a custom skill activation system with keyword triggers, intent patterns, and file context matching per repository. This was superseded by Claude Code's built-in skills system, which manages skills globally via `~/.claude/skills/` (Syncthing-synced across machines).

## Current Approach

Skills are now defined globally in `~/.claude/skills/` and automatically available across all projects. See `~/.claude/README.md` for details.

## See Also

- [Claude Code Hooks](hooks.md) - Active hooks system documentation
