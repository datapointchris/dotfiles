# `git checkout` vs `git switch` vs `git reset`

| Action                        | Old Command                    | New Command                            |
| ----------------------------- | ------------------------------ | -------------------------------------- |
| Switch to a branch            | `git checkout branch-name`     | `git switch branch-name`               |
| Create and switch to a branch | `git checkout -b new-branch`   | `git switch -c new-branch`             |
| Restore file changes          | `git checkout -- file.txt`     | `git restore file.txt`                 |
| Restore file from commit      | `git checkout HEAD~1 file.txt` | `git restore --source=HEAD~1 file.txt` |
| Unstage a file                | `git reset HEAD file.txt`      | `git restore --staged file.txt`        |
