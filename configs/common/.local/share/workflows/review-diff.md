---
tags: [review, claude, ai, git, diff, diffview, nvim, tmux, learning, recipe, workflow]
---

# review-diff — read the code you didn't type (diff left, Claude right)

```bash
# GOAL: close the comprehension loop. Committing straight to main means nothing
# ever brings you back to code the agent wrote. This is the thing that does.
# It is NOT a bug hunt — `/code-review` does that. This one is for understanding.

# THE WHOLE THING
review-diff           # from inside any repo: opens a `review` window, two panes
prefix + r            # same, without leaving the pane you're in (prefix = C-Space)

#   left  = nvim + DiffviewOpen on the range
#   right = claude, already started on /review-diff <range>
#   C-Left / C-Right cross between them (vim-tmux-navigator)

# WHAT RANGE IT PICKS
review-diff           # everything since your last `menu review done review-diff`
review-diff working   # uncommitted changes — the pre-commit case
review-diff HEAD~5..HEAD    # an explicit range
review-diff a3f2c1          # one commit
review-diff range           # just print what it would review, then exit

# WHILE YOU'RE READING — point at the screen instead of describing it
#   In the Claude pane, say "explain what I'm looking at" / "this hunk".
#   Claude runs `review-diff here`, which asks the review nvim over its socket
#   for file:line under your cursor, then reads the real file for context.
review-diff here      # file:line under the cursor (what Claude calls)

# CLOSE THE LOOP
menu review done review-diff   # advances the watermark; next run starts here
```

## What the session actually does

```text
1. triage   one table: read-closely vs skim, with the reason. You pick.
2. walk     intent → the 2-4 structural moves → the language idiom, named
3. quiz     OFF by default. Say "quiz me" to turn it on, then it stops dead
            after each question until you answer.
4. harvest  idiom you didn't know   → capture-note  (~/notes/dev/)
            something that looks wrong → capture-item (an icb item)
            a decision worth keeping   → .planning/status.md
```

## Gotchas

```bash
# - It never offers to fix what it finds. That's deliberate: a fix offer puts you
#   back in delegation mode, which is the habit the review exists to interrupt.
#   Findings become items.
# - The watermark is fleet-wide: ~/.local/state/menu is a Syncthing folder, so
#   marking it done on one box moves the next range on all of them. menu stores a
#   date and commits carry a time, so same-day commits show up once more. Better
#   than rounding the other way and dropping them.
# - Both panes closing takes the window with it. Quit nvim and exit Claude and
#   you're back where you were.
# - No `menu` or no `jq` → falls back to a 7-day window and says so on stderr.
```

Related: `ai-review-and-commit` (the loop this plugs into), `git-diff-viewing`
(delta ranges/word-diff), `claude-at-the-prompt` (the other ways in).
