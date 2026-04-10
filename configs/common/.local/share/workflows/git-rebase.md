# git rebase — interactive workflow

```bash
# Start interactive rebase
git rebase -i HEAD~3              # rebase last 3 commits
git rebase -i main                # rebase current branch onto main
```

Actions (change the word before each commit hash):

| Action | Effect                                          |
| ------ | ----------------------------------------------- |
| pick   | keep commit as-is                               |
| reword | keep commit, edit message                       |
| squash | merge into previous commit, combine messages    |
| fixup  | merge into previous commit, discard this message|
| edit   | pause after commit for amending                 |
| drop   | remove commit entirely                          |

Reorder commits by reordering the lines. Delete a line = drop that commit.

```bash
# During a conflict
git status                        # see which files conflict
# fix the conflicting files, then:
git add <files>
git rebase --continue             # move to next commit
git rebase --abort                # cancel entire rebase

# Rebase onto main (update branch with latest main)
git switch my-branch
git fetch origin
git rebase origin/main

# After rebase, force push is required for remote branches
git push --force-with-lease       # safer than --force
```
