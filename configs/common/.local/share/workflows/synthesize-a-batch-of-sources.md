---
tags: [relate, synthesis, research, content, cross-analysis, recipe]
---

# synthesize a batch of sources (relate: many URLs → cross-analyzed themes)

```bash
# GOAL: you have a pile of related sources — a YouTube playlist, or a text file
# of article/video URLs on one topic — and you want relate to analyze each AND
# cross-analyze them into shared themes + novel contributions, then explore the
# result. This is the batch pipeline, start to finish.

# 1. KICK OFF the batch — analyzes every source, then clusters them
relate batch <playlist-url>            # a YouTube playlist, OR...
relate batch ./urls.txt                # ...a text file, one URL per line

# 2. LET IT SETTLE, then check what's pending
relate status                          # DB state: pending batches, unviewed
                                       # items, and the SUGGESTED NEXT ACTION.
                                       # This is your dashboard between steps —
                                       # it tells you whether to resume or read.

# 3. RUN the meta-analysis on the cluster (if status shows it pending)
relate resume                          # cross-analyzes the batch into themes and
                                       # saves the synthesis. Skip if step 1
                                       # already finished the cluster.

# 4. READ + EXPLORE the synthesis
relate browse                          # fzf over content + analyses, interactively
relate show <id>                       # render one analysis via glow
relate search 'query'                  # full-text across everything analyzed

# 5. CALIBRATE — close the loop between your judgment and Claude's
relate rate <id>                       # your own score + optional review
relate deltas                          # where YOUR rating and Claude's quality
                                       # score disagree MOST — the items worth a
                                       # second look. This is the payoff of rating.
```

## The single-source detour

```bash
relate analyze <url> --discuss   # one URL, and open an interactive Claude session
                                 # to dig into it (critical analysis + personal
                                 # connections) instead of just saving a summary.
relate analyze <url> --no-save   # throwaway — analyze without touching the DB.
```

## Gotchas

```bash
# - `analyze` = ONE url. `batch` = a playlist/file, AND it cross-analyzes.
#   For a topic you want SYNTHESIZED, always batch — a pile of single analyses
#   never gets cross-linked into themes.
# - After batch, check `relate status` before assuming it's done — a large
#   cluster's meta-analysis is the separate `resume` step it points you to.
# - `rate` feels optional but it's what makes `deltas` useful later; rating as
#   you read is what surfaces your blind spots vs Claude's.
```

Also available as MCP tools (`relate` server) — the CLI is for driving the
pipeline; MCP is for pulling analyses into a Claude session.
