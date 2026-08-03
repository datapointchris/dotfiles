---
tags: [jira, issue, ticket, sprint, transition, work, cloud, bbkt, reference]
---

# jira — issues without the web UI (work box)

```bash
# GOAL: triage, read and transition Jira issues from the terminal. `bbkt` is the
# pull request half of this loop — `workflows show review-and-merge-a-pr-with-bbkt`.

# THE ONE COMMAND. Everything else is a key press inside the table.
jira issue list -a$(jira me)
```

Memorising flags is the wrong goal. `list` opens an **interactive table** and the
work happens in there — including `?`, which prints the whole key map. Learn the
keys once and the flags stop mattering.

## Inside the table

```text
j k h l / arrows   move          g G   top / bottom
v                  view the selected issue in full
m                  transition it — pick the new status from a list
c                  copy the issue URL      CTRL+k   copy just the KEY
CTRL+r  or  F5     refresh
?                  the full key map        q / ESC  quit
```

`CTRL+k` is the one that earns its keystroke: it puts `PROJ-123` on the clipboard,
which is what you need to name a branch so Bitbucket links the PR back to Jira.

## Narrowing the list

Only worth reaching for when the table is too big to scroll:

```bash
jira issue list -a$(jira me) -s~Done   # ~ is NOT — drop everything finished
jira issue list --created -7d          # -1h, week, month all work
jira sprint list --current -a$(jira me)   # just the sprint running now
jira issue list -q "summary ~ parser"  # JQL, when the flags run out
jira issue list -w                     # issues you're watching
```

Statuses are whatever your board calls them, so `-s"In Progress"` is instance
specific — `-s~Done` is the form that survives a workflow rename.

## Straight at one issue

```bash
jira issue view PROJ-123               # description, comments, linked branches/PRs
jira issue move PROJ-123 "In Progress" # transition without the table
jira issue assign PROJ-123 $(jira me)
jira issue create                      # interactive prompts
jira open PROJ-123                     # give up, open the browser
```

## Piping it somewhere

```bash
jira issue list --plain --no-headers   # the table is interactive by DEFAULT,
jira issue list --csv                  # so anything scripted needs --plain
jira issue list --raw                  # the raw API JSON
```

## Setup, once per machine

```bash
# 1. Jira profile picture -> Manage account -> Security -> Create API token
# 2. Export it — ~/.env is the uncommitted per-machine file .zshrc sources first
echo 'export JIRA_API_TOKEN="..."' >> ~/.env
# 3. Cloud, then site URL and the email the token belongs to
jira init
```

## Gotchas

```bash
# - The token is an ATLASSIAN API token, not your password, and it pairs with the
#   email address — Cloud rejects the token alone. bbkt's token is a separate
#   Bitbucket one; the two systems share a company, not a credential.
# - `$(jira me)` is a subshell call on every run. It's the documented idiom, but
#   it does hit the API — in a loop, resolve it once into a variable.
# - `-a` with no space: `-a$(jira me)`, not `-a $(jira me)`. Most short flags in
#   this CLI are written glued to their value.
# - `c` (copy URL) needs xclip or xsel on Linux. `CTRL+k` (copy key) does not.
# - Work box only. Jira does not exist on the personal machines, which is why
#   this is installed from the wsl-work-workstation manifest and nowhere else.
```
