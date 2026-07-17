---
tags: [gh, github, pr, pull-request, review, merge, ci, recipe]
---

# review and merge a PR from the terminal (gh: find → run it → approve → merge)

```bash
# GOAL: take a pull request from "haven't looked" to merged without leaving the
# terminal — and actually RUN the code, not just read the diff, before approving.

# 1. FIND it
gh pr list                 # open PRs in this repo (number, title, branch)
gh pr status               # or: PRs relevant to YOU (yours + review-requested)

# 2. INSPECT before checking out
gh pr view 42              # description, commits, review state, linked issues
gh pr diff 42              # the full diff in the pager
gh pr checks 42            # CI status — is it green? Don't review red without
                           # knowing why it's red.

# 3. RUN IT — the reason to review in the terminal at all
gh pr checkout 42          # checks out the PR branch locally. Now build it, run
                           # the tests, exercise the change. Reading a diff tells
                           # you it compiles; running it tells you it works.

# 4. REVIEW — leave the verdict
gh pr review 42 --approve
gh pr review 42 --request-changes -b "the retry loop never breaks on 429"
gh pr review 42 --comment  -b "works, one nit inline"

# 5. MERGE + clean up
gh pr merge 42 --squash --delete-branch
#   --squash  collapse the PR to one commit (or --merge / --rebase to taste)
#   --delete-branch  removes the remote branch so it doesn't linger
```

## The whole thing

```bash
gh pr checkout 42  →  test it locally  →  gh pr review 42 --approve
gh pr merge 42 --squash --delete-branch
```

## Gotchas

```bash
# - `gh pr checkout 42` SWITCHES your working branch to the PR. Get back with
#   `git switch -` (or gsw) when you're done — it doesn't return you automatically.
# - Check CI (`gh pr checks`) BEFORE merge, not after. `gh pr merge` will happily
#   merge a PR whose checks are still running unless branch protection blocks it.
# - Pick the merge strategy deliberately: --squash for a tidy history (one commit
#   per PR), --rebase to keep each commit, --merge for a merge commit. Your call
#   per repo's convention.
# - No PR number → gh acts on the PR for the CURRENT branch. `gh pr view` with no
#   number only works when you're already ON a PR branch.
```
