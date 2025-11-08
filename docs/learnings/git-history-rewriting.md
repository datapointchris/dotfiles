# Git History Rewriting: Just Remove the File Going Forward

**Date**: 2025-11-07
**Context**: Accidentally committed build binaries, used `git filter-branch` to clean history, created 270-commit divergence

## The Problem

Committed binary build artifacts (`tools/menu-go/menu`, `tools/sess/sess`), then attempted to clean history with `git filter-branch`:

```bash
# DON'T DO THIS on pushed commits
git filter-branch --tree-filter 'rm -f tools/*/menu tools/*/session' HEAD
```

**Impact**:

- All 270 commits got new SHA hashes (parent hash cascade)
- Local and remote histories diverged completely
- Required force-push to resolve
- Would break all collaborators in a shared repo

## The Solution

Just remove the file and move on - don't rewrite history:

```bash
# Simple, safe, works with shared repos
git rm tools/*/menu tools/*/session
echo "tools/*/menu" >> .gitignore
echo "tools/*/session" >> .gitignore
git commit -m "chore: remove accidentally committed binaries"
git push
```

The binary stays in one historical commit, but no history rewriting, no divergence, no force-push needed.

## Key Learnings

- **NEVER rewrite pushed history** - treat pushed commits as immutable
- **Parent hash cascade** - changing one commit rewrites ALL descendants
- **Simpler is better** - removing a file is easier than rewriting 270 commits
- **Force-push breaks teams** - all collaborators must re-clone or reset
- **Follow the rules in CLAUDE.md** - git safety protocol exists for this reason

## When History Rewriting IS Acceptable

- Personal feature branches before creating PR
- Secrets/credentials leaked (coordinate team force-push)
- Repository corruption (last resort)

## Related

- See `CLAUDE.md` Git Safety Protocol for complete rules
- BFG Repo-Cleaner is faster than filter-branch (but still requires force-push)
- GitHub has special handling for leaked secrets: `git-filter-repo` + support ticket
