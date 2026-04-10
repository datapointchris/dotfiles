# git log — useful formats and filters

```bash
# Compact views
git log --oneline                 # short hash + subject
git log --oneline --graph         # with branch/merge visualization
git log --oneline -10             # last 10 commits

# Detailed views
git log -p                        # show full diffs
git log --stat                    # show files changed + insertions/deletions
git log --name-only               # just list changed filenames

# Filter by time
git log --since="2 weeks ago"
git log --after="2024-01-01" --before="2024-02-01"

# Filter by author/content
git log --author="chris"
git log --grep="fix"              # search commit messages
git log -S "functionName"         # commits that add/remove string (pickaxe)
git log -G "regex"                # commits where diff matches regex

# Filter by path
git log -- src/auth/              # commits touching files in path
git log --follow file.txt         # track file across renames

# Compare branches
git log main..feature             # commits in feature not in main
git log main...feature            # commits unique to either branch

# Custom format
git log --pretty=format:"%h %an %ar %s"   # hash, author, relative date, subject
```
