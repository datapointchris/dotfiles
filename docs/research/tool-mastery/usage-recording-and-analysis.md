---
icon: material/chart-line
---

# Usage Recording & Analysis

**Job 2 of 3.** The question: *"What am I actually doing, and where am I doing it the slow
way?"* This is the "record everything I do in the terminal and analyze it for improvements"
idea from the original request.

The headline finding: **you are already recording.** `EXTENDED_HISTORY` and `SHARE_HISTORY`
are on, timestamps and durations are captured, and 10,051 entries sit in
`~/.local/state/zsh/history`. The gap is analysis, not capture. And a second finding: **no
off-the-shelf "weekly efficiency coach" exists** — the real path everywhere is
*capture → SQL/aggregate → optional LLM pass → digest*. The question is how much richer you want
the capture to be.

Research date: 2026-07-07.

!!! note "Built (2026-07-08)"
    The LLM coach described below now exists. **atuin** was adopted as the capture layer (SQLite;
    command, exit, cwd, session — the metadata the flat history lacks), and the **`/flow-review`**
    skill is the analysis pass: it reads atuin + the user's own aliases/functions/tools/workflows,
    finds inefficiencies, and codifies the accepted fixes. One caveat the "use what you have" section
    below understates: imported flat history has no cwd/exit/session, so the sequence and
    per-directory analysis only works on commands captured *after* atuin was installed, and ramps
    over time. See `docs/apps/menu.md` and `~/.claude/skills/flow-review/`.

## What your own history already reveals

Run against your real 10k-line history — this *is* the analysis idea, demonstrated:

- **Top exact commands:** `gst` 629, `risky` 582, `exit` 466, `ls` 418, `git push` 393,
  `clear` 363, `nvim` 191, `reload` 145, `z dot` 130, `btop` 118.
- **The dev-loop distortion:** `font` (661) and `theme` (530) dominate raw frequency because you
  were *building* them — test loops, not daily use. **This is the central analysis lesson: raw
  frequency conflates "I develop this" with "I use this."** Any useful analysis must weight or
  filter (e.g. exclude commands run inside `~/tools/font`, or discount rapid identical repeats).
- **Real inefficiencies, visible now:** `git push`/`git pull`/`git diff` typed in full hundreds
  of times with no short alias (you alias `gst` but not these — a `gp`/`gl`/`gd` gap);
  `clear` 363× + `reload` 145× + `exit` 466× = heavy manual session churn worth a look;
  2,774 distinct commands / 10k total = very high diversity, the exact profile that forgets its
  own surface area.

Your existing `tool-usage` app already does a primitive version of this (grep-count a registry-derived
tool list). The findings above are what a *real* analysis layer adds on top.

## Capture options, from "use what you have" to "capture everything"

### Level 0 — your existing zsh history (free, already on)

Zsh extended-history format is `: <epoch>:<duration>;<command>`. That gives you command,
timestamp, and duration already. What it *lacks*: exit code, working directory, and clean
separation of sessions. The plain-shell idiom for a quick glance:

```bash
sed -E 's/^: [0-9]+:[0-9]+;//' ~/.local/state/zsh/history \
  | awk '{print $1}' | sort | uniq -c | sort -rn | head -30
```

Your `tool-usage` app is a curated version of this. It can be upgraded in place (see below)
without adopting anything new — the cheapest path.

### Level 1 — atuin (richest capture, SQLite, the recommended base if you go further)

[github.com/atuinsh/atuin](https://github.com/atuinsh/atuin). Replaces the flat history file
with a SQLite DB. Per-command it records **command, exit code, cwd, hostname, session, duration
(ns), timestamp (ns)** — everything the flat file is missing:

```sql
CREATE TABLE history (
  id text primary key, timestamp integer, duration integer, exit integer,
  command text, cwd text, session text, hostname text, deleted_at integer
);
```

- **Local-first:** works fully offline; optional **end-to-end-encrypted sync** across your
  machines. Self-hosting the sync server is a small Rust binary + Postgres — and it *cannot read
  your history* (encrypted client-side), which matters because history contains secrets/paths.
  Fits your homelab model.
- **`atuin stats`** gives most-used / total / unique / longest-running, scopeable by natural
  language (`atuin stats last friday`). Shallow but a good weekly glance.
- **The real power is SQL over the DB** — see the query library below. Simon Willison opens it
  directly in Datasette.
- **Caveats:** the local schema is explicitly *not* guaranteed stable (fine for personal
  queries, a risk for tooling you'd maintain long-term); reported slowdowns at 80k+ commands.

**Fit:** the single best capture base if you want cwd/exit/duration — which are exactly what
turn "what's frequent" into "what's *slow* and what *fails*."

### Alternatives to atuin

- **[zsh-histdb](https://github.com/larkery/zsh-histdb)** — zsh-only, SQLite, a clean normalized
  schema (commands / history / places) that is *pleasant* to query, plus `histdb-top` and
  `histdb-top dir`. No encrypted sync (cross-machine SQLite merge is painful). Best if you want
  queryable capture without atuin's Ctrl-R takeover.
- **[resh](https://github.com/curusarn/resh)** — captures a unique signal no one else does:
  **whether a command was recalled from history or typed fresh**, plus git remote. That flag
  directly detects "you retype this instead of aliasing/recalling it." JSON-lines storage
  (pipe to `jq`/DuckDB). Downside: largely dormant.
- **[mcfly](https://www.nickyt.co/blog/i-switched-shell-history-tools-heres-why/)** — great
  neural Ctrl-R, but no exit/duration/stats. Not an analysis base.
- **[hstr](https://github.com/dvorka-oss/hstr)** — frequency suggest-box over the flat file;
  no exit/duration/cwd. Recall tool, not a report tool.

## The analysis layer (this is the part nobody ships — you build it)

Whatever the capture, the insight comes from a handful of aggregate queries. Over atuin's DB:

```sql
-- Most-run commands (the "what dominates my day" view)
SELECT command, count(*) c FROM history GROUP BY command ORDER BY c DESC LIMIT 30;

-- Slowest habitual commands (the surprise-win view — "I thought this was fast")
SELECT command, count(*) n, avg(duration)/1e9 avg_s
FROM history GROUP BY command HAVING n > 20 ORDER BY avg_s DESC;

-- Failure-prone commands (where you keep getting syntax wrong)
SELECT command, count(*) fails FROM history WHERE exit != 0
GROUP BY command ORDER BY fails DESC;

-- Per-directory habits (what you run *here* — feeds project-scoped cheats)
SELECT cwd, command, count(*) c FROM history GROUP BY cwd, command ORDER BY c DESC;
```

The three insight types that matter for *your* goal:

1. **Alias candidates** — long commands typed often (`git push` 393×). `[lazy](https://github.com/AndrewRPorter/lazy)`
   and `[topalias](https://github.com/meteoritt/topalias)` generate these suggestions from
   history automatically; or the SQL above plus a length filter.
2. **The forgotten-tools complement** — the query no tool ships but atuin makes trivial: *tools
   that exist in your dotfiles but are absent (or rare) in history.* `SELECT` your tool names
   (from `~/dev/tools.yml`), LEFT JOIN against history counts, surface the zeros. This is the
   literal "tools I forget I have" report, and it feeds Job 3's review queue.
3. **Slow/failing patterns** — the `avg_s` and `exit != 0` queries surface where you're wasting
   time or fumbling syntax.

### LLM-assisted review (the "you do X the slow way" coach)

No turnkey product exists, but the building blocks are mature and this is a very buildable gap:

- **Export a table, hand it to a model.** `sqlite3 history.db "…top/slow/failed…" | llm "suggest
  aliases and faster equivalents for these"`. Use a **local model via Ollama** given history
  contains tokens/paths.
- **[Atuin History MCP server](https://skywork.ai/skypage/en/atuin-history-ai-command-line/1981676465415098368)**
  — exposes the history DB to an agent, so Claude/an LLM can *query your habits directly* and
  reason about them. This is the most on-point emerging piece: a periodic "review my last two
  weeks and tell me what to improve" agent run.
- Adjacent: [ShellGPT](https://github.com/ther1d/shell_gpt), [Butterfish](https://butterfi.sh/)
  (injects recent history into context).

**This is arguably the highest-value build in the whole project**: a scheduled job (or a
`claude` invocation) that reads the analysis tables and produces a short markdown digest —
"this week you typed `git push` 393×, add `gp`; `terraform plan` averaged 40s, 12 runs failed
on the same auth error; you haven't touched `safekeep` in 6 weeks." It ties Job 2 (data) to Job
3 (what to drill).

## Upgrading `tool-usage` without adopting anything

`tool-usage` can grow into the analysis layer with no new dependency:

- ~~Read tool names from `~/dev/tools.yml` instead of a hardcoded list~~ — **done**: it now
  derives the `custom-tools` list from the registry, so it auto-stays-current.
- Add the **complement report** — tools in the registry with zero/low history hits ("forgotten").
  (`tool-usage` already prints a "Never used" section; extend it to low-but-nonzero and by date.)
- Add **last-used dates** (you already have `EXTENDED_HISTORY` timestamps) so "haven't used in N
  days" works.
- Optionally add an alias-candidate pass (long commands, high frequency, no matching alias).

That is a meaningful chunk of Job 2 with no new dependency. Adopting atuin is the upgrade when
you want cwd / exit / duration and cross-machine capture.

## Recommendation shape

- **Minimum:** upgrade `tool-usage` to read the registry, report the forgotten-tools complement,
  and add last-used dates. Uses data you already have.
- **If you want real efficiency insight:** adopt **atuin** (local-first, encrypted self-hosted
  sync via homelab), keep the flat history as fallback, and write the four aggregate queries as
  a small `history-report` script.
- **The differentiator:** an **LLM pass** (local Ollama or a scheduled `claude` run over the
  atuin MCP) that turns the tables into a plain-English weekly "here's what to fix" digest. This
  is the thing that doesn't exist off the shelf and is the closest to the original vision.

## Sources

- atuin — <https://github.com/atuinsh/atuin> · stats <https://docs.atuin.sh/cli/reference/stats/> · schema/DB path <https://til.simonwillison.net/macos/atuin> · review <https://jpk.io/dev-tools/atuin-shell-history-review/> · MCP <https://skywork.ai/skypage/en/atuin-history-ai-command-line/1981676465415098368>
- zsh-histdb — <https://github.com/larkery/zsh-histdb> · query fns <https://news.ycombinator.com/item?id=29155825>
- resh — <https://github.com/curusarn/resh> · mcfly <https://www.nickyt.co/blog/i-switched-shell-history-tools-heres-why/> · hstr <https://github.com/dvorka-oss/hstr>
- alias candidates — lazy <https://github.com/AndrewRPorter/lazy> · topalias <https://github.com/meteoritt/topalias>
- LLM glue — ShellGPT <https://github.com/ther1d/shell_gpt> · Butterfish <https://butterfi.sh/>
- context — <https://tratt.net/laurie/blog/2025/better_shell_history_search.html> · <https://lobste.rs/s/zfcis3/shell_history_is_your_best_productivity>
