# git cherry-pick — apply specific commits

```bash
# Pick a single commit onto current branch
git cherry-pick abc1234

# Pick multiple commits
git cherry-pick abc1234 def5678
git cherry-pick abc1234..def5678  # range (exclusive of first)
git cherry-pick abc1234^..def5678 # range (inclusive of first)

# Options
git cherry-pick -n abc1234        # stage changes but don't commit
git cherry-pick -x abc1234        # append "cherry picked from" to message
git cherry-pick -e abc1234        # edit commit message before committing

# During a conflict
git status                        # see conflicting files
# fix conflicts, then:
git add <files>
git cherry-pick --continue
git cherry-pick --abort           # cancel entirely
git cherry-pick --skip            # skip this commit, continue with next

# Common patterns
# Backport a fix to a release branch
git switch release/1.2
git cherry-pick abc1234 -x

# Pull one commit from a feature branch
git switch main
git cherry-pick feature-branch~2  # 3rd commit from tip of feature-branch
```
