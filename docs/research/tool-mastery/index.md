---
icon: material/school
---

# Tool Mastery & Rediscovery

Research into the problem of **forgetting the tools you already own** — the custom CLIs in
`~/tools`, the `apps/` scripts in this repo, and the daily third-party tools (fzf, ripgrep,
git, tmux, neovim) whose efficient features never make it into muscle memory.

The goal is **not more apps or more note-taking**. It is consolidation: fewer, better tools,
actually memorized, actually combined. This directory collects the research, the prior art,
and the design options so decisions can be made deliberately.

Research date: 2026-07-07. Sources are cited inline in each document.

## The core reframe

The starting assumption was "I need a tool to record what I do and analyze it." The research
changed that framing. You do **not** have a missing-tool problem — you have a **fragmentation
and passivity** problem. The pieces already exist in this repo; they are scattered across five
front doors and are almost entirely *passive* (recognition), with no *active* (recall) layer.

Everything the research surfaced sorts into **three distinct jobs** that are currently
conflated. Separating them is the key move.

| Job | Question it answers | Memory mode | What you have today | The gap |
| --- | --- | --- | --- | --- |
| **1. Discovery / lookup** | "What do I have and how do I use it — right now?" | Recognition (long tail) | `workflows`, `cheat`, `tldr`, `toolbox`, `menu`, mkdocs site | 5–6 separate doors; nothing unifies them; mkdocs needs a browser |
| **2. Recording / analysis** | "What am I actually doing, and where am I slow?" | Measurement | zsh `EXTENDED_HISTORY` + `tool-usage` (grep) | Rich capture + real analysis ("you do X the slow way") |
| **3. Active review / retention** | "Drill me until it's automatic." | Recall (hot set) | `workflows motd` (random card on startup) | No active recall — only passive exposure |

The single most-cited principle across every thread: **look up the long tail, drill the hot
set.** Point-of-need lookup (Job 1) is correct for commands you use monthly. Spaced, active
recall (Job 3) is correct for the ~20 things you keep fumbling. A random tip on startup — what
you have now — is neither: it is recognition without scheduling, so it builds ambient
awareness but not retention.

## What you already have (the ecosystem map)

Grounding the research in the actual repo, because most recommendations graft onto existing
pieces rather than replacing them:

| Layer | Tool | State | Location |
| --- | --- | --- | --- |
| **Author** | `add-to-workflows` skill, `workflows new` | Working | `.claude/skills/`, `apps/common/workflows` |
| **Browse (personal cards)** | `workflows search` — fzf + bat over 32 cards | Working | `~/.local/share/workflows/*.md` |
| **Browse (tool catalog)** | `toolbox` — reads `~/dev/tools.yml` (69 KB) | Working | `~/tools/toolbox` |
| **Browse (federated)** | `menu` | Working — fzf search across tools registry + tagged workflows + skills, biased to name/tags, delegating display to each collection | `apps/common/menu` |
| **Browse (generic)** | `cheat` (community sheets), `tldr` | Working, but generic, not *yours* | `~/.config/cheat`, tealdeer |
| **Surface** | `workflows motd` → random card on shell startup | Working (the review you like) | `.zshrc` line ~437 |
| **Analyze** | `tool-usage` — grep frequency over history | Registry-driven list; raw counts only (no cwd/exit/duration) | `apps/common/tool-usage` |

Two concrete findings that surfaced here (both since fixed — see the consolidation doc):

- **`menu` was silently broken** and `tool-usage` used a hardcoded, already-stale tool list.
  Both now derive their list from the `custom-tools` category in `~/dev/tools.yml`
  (Syncthing-synced), and the eight uncatalogued personal tools were added to the registry.
- **You are already recording everything.** `EXTENDED_HISTORY`, `SHARE_HISTORY`, timestamps,
  and durations are on. 10,051 entries sit in `~/.local/state/zsh/history`. The gap is
  *analysis*, not capture — you do not need atuin to *start* (though it captures far more; see
  Job 2).

## What your real history already shows

A live demonstration of the Job-2 idea, run against your actual 10k-line history:

- **Top exact commands:** `gst` 629, `risky` 582, `exit` 466, `ls` 418, `git push` 393,
  `clear` 363, `nvim` 191, `reload` 145, `z dot` 130.
- **Signal vs. noise:** `font` (661) and `theme` (530) dominate raw frequency — but that is
  *dev/test looping* while building those tools, not daily use. **Raw frequency lies; the
  analysis layer must separate "I'm developing this" from "I use this."**
- **Concrete inefficiencies visible even now:** `git push` / `git pull` / `git diff` typed in
  full hundreds of times with no short alias (you alias `gst` but not these); `clear` 363× +
  `reload` 145× + `exit` 466× is heavy manual session churn; 2,774 distinct commands out of
  10k means very high diversity — exactly the profile that forgets its own surface area.

This is the proof-of-concept: *"you type `git push` 393 times — add `gp`"* is a finding your
current grep-based `tool-usage` cannot produce.

## The convergent architecture

Independently, four of the five research threads landed on the **same shape**: one source of
truth, deriving every layer, with no new note-taking app.

1. **Single source of truth** — descriptions live *inline* next to the thing they describe
   (alias `# comments`, tool `--help`, workflow front matter). Nothing is documented twice, so
   nothing drifts. This directly answers your "goes out of sync" complaint.
2. **Discovery surface** — one fzf keystroke fans out across that source of truth and drops the
   *real command* onto the prompt (so it enters history and reinforces itself).
3. **Anti-forgetting at point of use** — the real command stays visible (alias expansion,
   `precognition.nvim`), so lookups don't become permanent crutches.
4. **Ambient resurfacing** — the startup tip, upgraded from per-shell random to a **weekly
   "tool of the week"** cadence (sustained exposure beats novelty for mastery).
5. **Data for pruning + scheduling** — history analysis surfaces both dead weight (never used →
   cut) and forgotten keepers (in your dotfiles, absent from history → resurface).
6. **Memorization layer (optional, heaviest)** — active recall / spaced repetition over the
   hot set, cards auto-generated from the same inline source.

## How to read this directory

Each document is a menu of options with tradeoffs and use cases — not a plan. Decisions come
after.

- **[Discovery & the terminal docs browser](discovery-and-terminal-docs.md)** — Job 1. navi vs.
  cheat vs. um vs. DIY fzf; `help2man` / Cobra doc generation so your tools' docs can't drift;
  how to unify the five front doors into one. Addresses the "terminal browser for only my shit"
  idea.
- **[Usage recording & analysis](usage-recording-and-analysis.md)** — Job 2. atuin vs. histdb
  vs. resh vs. your existing history; the SQL that produces real insights; LLM-assisted review;
  the concrete findings from your own history.
- **[Active review & retention](active-review-and-retention.md)** — Job 3. The long-tail/hot-set
  principle; spaced repetition in the terminal; `zsh-you-should-use`; motd variants; why your
  current random-workflow setup is half the answer.
- **[Neovim mastery](neovim-mastery.md)** — the editor-side of all three jobs. `keymaps.nvim`
  (always-in-sync cheatsheet + usage stats), `hardtime.nvim`, `precognition.nvim`, and the
  build-your-own `vim.on_key` composition analysis.
- **[Consolidation architecture](consolidation-architecture.md)** — the synthesis. The
  single-source-of-truth pipeline, how each piece grafts onto what you already have, a phased
  path, and the open decisions to make together.
