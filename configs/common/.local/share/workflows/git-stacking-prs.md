# git stacking PRs — branch-on-branch workflow

Create a stack: `main → feature-a → feature-b → feature-c`

```bash
git switch main
git switch -c feature-a
# ... work, commit ...
git push -u origin feature-a

git switch -c feature-b           # branches off feature-a
# ... work, commit ...
git push -u origin feature-b
```

Open PRs: `feature-a → main`, `feature-b → feature-a`

```bash
# When feature-a gets updated (review feedback)
git switch feature-a
# ... make changes, commit, push ...

# Update feature-b with changes from feature-a
git switch feature-b
git rebase feature-a
git push --force-with-lease

# When feature-a merges to main
git switch feature-b
git rebase main                   # rebase onto main now
git push --force-with-lease
# Change PR base: feature-b → main (in GitHub UI)
```

**Keep stacks shallow** — 2-3 deep max.
**Merge from bottom up** — feature-a first, then feature-b.
