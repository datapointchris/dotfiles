# Claude Code Hooks & Git Workflow Reference

This repository uses universal hooks (from `~/.claude/`) for Claude Code automation, plus git pre-commit hooks for quality enforcement.

## Hook Organization

### Universal Hooks (`~/.claude/`)

Apply to all Claude Code projects. These hooks change frequently as workflow improvements are added.

**Location:** `~/.claude/hooks/`

See `~/.claude/README.md` for the current list of universal hooks and their purposes.

## Git Hooks (via pre-commit framework)

Git hooks are installed via the pre-commit framework and run for ALL commits.

### Installation

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit
```

### Conventional Commits Enforcement

**Required format:** `type(optional-scope): description`

**Valid types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`, `perf`, `build`, `ci`, `revert`

## Bypassing Hooks

All pre-commit hooks can be bypassed:

```bash
git commit -m "feat: quick fix" --no-verify
```

Or skip specific pre-commit hooks by name:

```bash
SKIP=markdownlint git commit -m "feat: docs coming later"
```

## Troubleshooting

### Hook Not Running

```bash
# Reinstall pre-commit hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type post-commit

# Test a specific hook
pre-commit run markdownlint --all-files
```

## Philosophy

1. **Atomic Commits**: Each commit is a complete, revertable unit of work
2. **Documentation Synchronization**: Code changes include their usage documentation
3. **Context Awareness**: Claude has relevant guidelines loaded automatically
4. **Bypassable When Needed**: All checks can be skipped with `--no-verify`

## See Also

- [Claude Code Hooks Guide](https://docs.anthropic.com/en/docs/claude-code/hooks) - Official documentation
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message standard
- [pre-commit framework](https://pre-commit.com/) - Git hook management
