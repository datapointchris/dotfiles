---
tags: [risky, ai, claude, review, git, commit, recipe, workflow]
---

# ai-review-and-commit — your #1 loop (Claude edits, you verify, you commit)

```bash
# GOAL: turn a yolo Claude session into clean, reviewed, conventional commits.
# `risky` = `claude --dangerously-skip-permissions` — it edits WITHOUT asking,
# so the review step is not optional: it is the whole point of the loop.

# 1. LAND in the repo
z <repo>              # zoxide jump (cd is aliased to z)

# 2. RUN the agent
risky                 # start a fresh --dangerously-skip-permissions session
risky --resume        # OR pick up an existing session (keeps context)
                      # ...let it make the changes, then quit back to the shell.

# 3. SEE what it did (never commit blind)
gst                   # git status — the file-level overview (alias: git status)
git diff              # full diff — pipes through delta automatically (pager)
lazygit               # OR go visual: hunk-level review, stage/unstage per hunk,
                      #   'e' to edit a hunk, space to stage. Best for big diffs.

# 4. STAGE deliberately — one logical change per commit
ga                    # forgit: fzf-pick files/hunks with live preview
git add -p            # OR raw patch mode if you want the plain prompts
                      # DO NOT `git add -A` — the CLAUDE.md rule; stage explicitly.

# 5. COMMIT conventional
git commit            # opens editor: feat|fix|docs|chore|refactor|test|perf|ci
                      #   imperative, ≤50-char subject, body for the WHY.
                      # (see the git-conventional-commits card for the full spec)

# 6. SHIP (only when you mean to)
gp                    # git push  — never automatic; push when it's ready
```

## The whole thing in two lines (the common case)

```bash
z <repo> && risky              # ...agent works...
gst → git diff → ga → git commit → gp
```

## Gotchas

```bash
# - risky skips ALL permission prompts. If you didn't read the diff, you didn't
#   review it. Step 3 is the safety you traded away at step 2.
# - Split unrelated changes into separate commits. If the agent touched three
#   things, that's three `ga`→`git commit` passes, not one `git add -A`.
# - `git diff` shows UNSTAGED only. After `ga`, use `git diff --staged` to see
#   what's actually going into the commit.
# - Push is step 6, not step 5. Committing ≠ pushing; keep them separate so a
#   bad commit is a local fix, not a force-push cleanup.
```

Related: `forgit-git` (the `ga`/`gd`/`glo` picker family), `git-conventional-commits`
(the message format), `git-diff-viewing` (delta ranges/word-diff).
