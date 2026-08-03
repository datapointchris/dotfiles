---
tags: [bbkt, bitbucket, pr, pull-request, review, merge, diff, develop, uat, prod, work, recipe]
---

# open and review a PR on Bitbucket (bbkt + git, work box)

```bash
# GOAL: raise a PR against develop/uat/prod and review one, without ever making a
# local copy of those branches. `bbkt` for the PR lifecycle, git for the diff.
# The GitHub/gh version of this is `workflows show review-and-merge-a-pr`.
# The Jira half of this loop is `workflows show jira-from-the-terminal`.

# 0. REFRESH the remote refs. syncer does this on every run, so usually it's done.
git fetch --prune

# 1. YOUR OWN PR — check what you're about to ask for before you ask
git diff origin/develop...HEAD | delta         # what my branch adds
git diff --stat origin/develop...HEAD          # just the file list
nvim -c 'DiffviewOpen origin/develop...HEAD'   # side-by-side review

bbkt pr create                                 # from the checked-out branch
bbkt pr create --target uat                    # override the config default
bbkt pr create --reviewer alice --reviewer bob

# 2. SOMEONE ELSE'S PR — find it, read it, run it
bbkt pr list --reviewing        # awaiting YOUR review, across every repo
bbkt pr list --mine             # authored by you, across every repo
bbkt pr list                    # open PRs in this repo
bbkt pr view 42                 # title, branches, reviewers — and prints the
                                # exact `git diff` for THAT PR's branches

git diff origin/develop...origin/feature/PROJ-123 | delta   # both refs remote
git switch feature/PROJ-123     # to actually RUN it: git creates the local
                                # branch from origin/ automatically (DWIM)

# 3. VERDICT + MERGE
bbkt pr approve                 # defaults to this branch's PR
bbkt pr merge 42
bbkt pr open --print            # the web URL, when a human needs a link
```

## Just browsing what's on a branch

No checkout, no local branch, works offline after any fetch:

```bash
git log --oneline origin/uat            # what's on uat right now
git show origin/uat:path/to/file        # a file as it exists on uat
git log --oneline origin/prod..origin/uat   # in uat, not yet in prod
git diff origin/uat origin/prod         # full tree comparison
```

## Two dots vs three — the one thing to memorise

```text
origin/develop...HEAD   from the MERGE BASE. What my branch ADDS. <- PR view
origin/develop..HEAD    tip to tip. Also shows everything that landed on develop
                        after I branched, backwards, as if I'd deleted it.
```

Three dots is what Bitbucket's web view renders, so it's the one that matches the
PR. Mnemonic: **three dots = three-way merge = the PR**.

## Gotchas

```bash
# - NEVER `git switch develop && git pull` just to diff against it. A local
#   develop you don't work on is pinned at whenever you made it — after a
#   teammate pushes, browsing it silently shows yesterday's develop while
#   looking like a perfectly normal branch. `origin/develop` is always current
#   after any fetch, needs no local branch, and never drifts.
# - `git fetch` already brings down EVERY branch on the remote. origin/develop,
#   origin/uat and origin/prod exist in a fresh clone you've only ever had main
#   checked out in. There is nothing to set up.
# - Order matters: `git diff origin/develop...HEAD`, target FIRST. Backwards
#   shows the diff inverted (additions as deletions).
# - `git switch feature/x` with no local branch auto-creates it tracking
#   origin/feature/x. That's the right way to get onto someone's PR to run it —
#   and it's fine, because you WILL work on it. Get back with `git switch -`.
# - Only a PERSONAL Bitbucket token can merge. Project- and repo-scoped tokens
#   can't: a merge creates a commit, which needs a real user identity.
# - Bitbucket Data Center, not Cloud. Every Bitbucket CLI you find online targets
#   Cloud's REST 2.0 and will not work. That's why bbkt exists.
```
