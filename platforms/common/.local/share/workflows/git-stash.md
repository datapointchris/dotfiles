# git stash — save and restore uncommitted work

```bash
# Stash current changes (staged + unstaged tracked files)
git stash                         # default message
git stash push -m "wip: auth"     # descriptive message

# Stash options
git stash -u                      # include untracked files
git stash -a                      # include untracked + ignored
git stash push path/to/file       # stash specific files only

# Restore stashed changes
git stash pop                     # apply most recent + remove from list
git stash apply                   # apply most recent, keep in list
git stash pop stash@{2}           # apply specific stash

# Browse stashes
git stash list                    # show all stashes
git stash show                    # diff summary of latest
git stash show -p                 # full diff of latest
git stash show stash@{1} -p      # full diff of specific stash

# Clean up
git stash drop                    # remove most recent
git stash drop stash@{2}          # remove specific stash
git stash clear                   # remove ALL stashes (careful)

# Create branch from stash
git stash branch new-branch       # create branch, apply stash, drop it
```
