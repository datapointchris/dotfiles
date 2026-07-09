---
icon: material/vector-combine
---

# Consolidation Architecture

The synthesis of the three jobs into one coherent system that **shrinks** your tool surface
rather than adding to it. This is the "think through the whole thing" document: how the pieces
fit, how they graft onto what you already have, a phased path, and the open decisions to make
together.

The philosophy that frames it all, and it is nearly unanimous in the literature: **the point of
this system is to consolidate.** Audit what you use → for each job keep one tool → master the
real commands → alias/abbreviate only the high-frequency ones → make the survivors discoverable
so they are never re-forgotten. Every memory-serious source (the "aliases sparingly" atrophy
argument, the "one tool per job" digital-minimalism rule, the HN "learn a few primitives deeply"
consensus) points the same direction. Accumulation is the anti-pattern you already sensed.

Research date: 2026-07-07.

!!! note "Build status (2026-07-08)"
    Partially built. `menu` unifies the discovery doors; the retention layer (job 3) was rebuilt
    by **removing** the `workflows motd` random card and replacing it with the `menu review`
    register + a first-shell-of-each-half-day nudge. The "upgrade the motd to weekly rotation"
    lines below are superseded by that replacement. See `docs/apps/menu.md`.

## The single-source-of-truth pipeline

Four independent research threads converged on the same architecture. Its defining property:
**every layer derives from one source, so nothing is documented twice and nothing drifts.** This
is the structural answer to your "it goes out of sync and there are too many front doors"
complaint.

```yaml
                    ┌─────────────────────────────────────────────┐
                    │            SINGLE SOURCE OF TRUTH            │
                    │  • alias/function files with `# comments`   │
                    │  • tool --help / Cobra command definitions  │
                    │  • workflow cards (idioms & combinations)   │
                    │  • ~/dev/tools.yml (the tool catalog)       │
                    └───────────────────┬─────────────────────────┘
                                        │ derives
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
   JOB 1: DISCOVERY              JOB 2: ANALYSIS               JOB 3: RETENTION
   one fzf keystroke →          history → SQL/LLM →           weekly rotation +
   real command on prompt       "fix X" digest +              nudge (YSU) +
   (unify the 5 doors)          forgotten-tools report        spaced recall (repeater)
        │                               │                               │
        └───────────────────────────────┴───────────────────────────────┘
                                        │ feeds back
                        Job 2's data chooses Job 3's hot set,
                        and surfaces Job 1's forgotten tools
```

The loop is the important part: **the analysis layer (Job 2) is what makes the other two
smart.** It tells discovery which tools you've forgotten (resurface them) and tells retention
which commands you keep fumbling (drill them). Without it, Job 1 and Job 3 are guessing.

## How it grafts onto what you already have

Most of this is *upgrade in place*, not *adopt new*. Mapping each job to existing repo pieces:

| Job | Existing piece | Graft |
| --- | --- | --- |
| **1 Discovery** | `workflows` (fzf+bat over 32 cards), `cheat`, `tldr`, `toolbox`, `menu` | Unify behind one keystroke; make selection **drop the real command on the prompt**; derive tool option-docs from Cobra `--help` (`menu` registry path already fixed ✓) |
| **2 Analysis** | `tool-usage` (registry-driven grep), zsh `EXTENDED_HISTORY` (already on) | `tool-usage` now reads the registry ✓; still to add: forgotten-tools report + last-used dates; optionally adopt `atuin` for cwd/exit/duration; add an LLM digest |
| **3 Retention** | `workflows motd` (random on startup) | Weekly rotation + first-shell gating; add `zsh-you-should-use` nudge; add `repeater` recall deck fed from workflow cards |
| **nvim** | "nvim skill" (find commands) | `keymaps.nvim` export as the always-in-sync cheatsheet; `hardtime.nvim` + `precognition.nvim`; `vimhjkl` drills |

**You are not starting from zero — you are ~60% built.** The work is convergence and the two
genuinely-missing layers (real analysis, active recall), not a new pile of tools.

## Two concrete fixes (done)

Both are complete — the first, smallest instance of the single-source-of-truth principle in
action:

1. **`menu` was broken** — it read `~/.config/toolbox/registry.yml`, which does not exist. Now it
   reads the `custom-tools` category from `${TOOLBOX_REGISTRY:-~/dev/tools.yml}` (the same
   resolution `toolbox` uses) and lists every personal tool with its description.
2. **`tool-usage` used a hardcoded, already-stale list** (it named `signal`, which does not
   exist, and missed `indy`/`relate`/`syncer`/…). It now derives the same `custom-tools` list
   from the registry, so it can never drift as tools are added or retired.

Alongside these, the eight uncatalogued personal tools (`indy`, `logsift`, `packages`, `relate`,
`syncer`, `tool-usage`, `webviewrs`, `zmk-build`) were added to the registry; `toolbox check` now
reports zero drift between registry, PATH, and disk.

## The genuinely-missing capabilities (the build targets)

Everything else is assembly of existing tools. These three do not exist off the shelf and are
where original work would go — in priority order by value-to-effort:

1. **The forgotten-tools report** *(low effort, high value).* A query: tools in `~/dev/tools.yml`
   with zero/low hits in history, or not used in N days. This is the literal "tools I forget I
   have" answer and it feeds the review queue. Buildable today as a `tool-usage` upgrade over
   your existing history; trivial as one SQL query if you adopt atuin.
2. **The LLM efficiency digest** *(medium effort, highest value).* A scheduled `claude`/Ollama
   run over the analysis tables that emits a plain-English weekly "here's what to fix" — alias
   candidates, slow commands, repeated failures, forgotten tools. This is the closest thing to
   the original "record everything and analyze it for improvements" vision, and nobody ships it.
3. **Command-composition analysis** *(higher effort, nvim-side).* An operator+motion state
   machine over `vim.on_key` (and/or a shell equivalent) to report *composed* usage — "you never
   use `ci(`." The only way to get the report you'd most want; no plugin does it.

## A phased path (menu of moves, not a commitment)

Ordered so each phase is independently valuable and low-regret. Decisions on scope come after.

- **Phase 0 — fix and consolidate (days).** ~~Repoint `menu`; make `tool-usage` read the
  registry~~ (done). Still: make `workflows search` drop the selected command onto the prompt
  (borrow the `zsh-cheatsheet` ZLE insert), and upgrade the motd to weekly-rotation +
  first-shell gating. *All in-place, no new tools.*
- **Phase 1 — the analysis layer (a week).** Add the forgotten-tools report to `tool-usage`
  (uses history you already have). This alone answers the core "I forget my tools" complaint.
- **Phase 2 — the nudge + recall layers (a week).** `zsh-you-should-use` in "after" mode with a
  small hardcore set for the git aliases your history shows you type long. Stand up `repeater`
  with a deck auto-generated from your workflow cards. Feed the deck from Phase 1's data.
- **Phase 3 — richer capture (optional).** Adopt `atuin` (local-first, encrypted self-hosted
  sync via homelab) for cwd/exit/duration; rewrite the analysis queries against its DB; add the
  LLM digest (build target #2).
- **Phase 4 — nvim (parallel track, any time).** `keymaps.nvim` export + `hardtime.nvim` +
  `precognition.nvim`; `vimhjkl` drills; composition analysis (build target #3) if you want it.

## Open decisions (for us to make together)

These are the forks the research surfaced but can't decide for you:

1. **Discovery: unify or adopt?** Extend `workflows` into the one front door (dotfiles-native,
   you own it), or adopt `navi`/`um` (more features, but a sixth door)? The research leans
   *unify* — you already own the pattern, and a new tool re-fragments.
2. **Capture: history or atuin?** Stay on the flat zsh history you already have + upgraded
   `tool-usage` (zero new deps, no cwd/exit/duration), or adopt atuin (rich capture, encrypted
   sync, but a schema-unstable dependency and a Ctrl-R takeover)? Depends on whether you want
   slow-command / failure / per-directory insight or just frequency.
3. **Retention intensity: nudge-only or full SR?** `zsh-you-should-use` + weekly motd is low
   effort and may be *enough*. `repeater`/`vimhjkl` add true recall but cost card-authoring and
   daily minutes. How much do you actually want to *drill* vs. just be *reminded*?
4. **Where the LLM digest runs.** A local Ollama job (private, history never leaves the machine)
   vs. a scheduled `claude` run over the atuin MCP (better model, but history — which holds
   secrets/paths — goes to the API). Privacy vs. quality.
5. **nvim scope.** Off-the-shelf (`keymaps.nvim` + `hardtime` + `precognition`) is likely
   sufficient. The composition-analysis build is a real project — worth it only if the
   "motions I never use" report genuinely motivates you.

## The one-sentence version

You have a fragmentation-and-passivity problem, not a missing-tool problem: **unify the five
discovery doors into one keystroke, add the analysis layer that tells you what you're forgetting
and doing slowly, add a scheduled-recall layer for the hot set that analysis identifies — and
let all of it derive from one source of truth so it stops going out of sync.** The result is
fewer tools, better memorized, which is exactly the consolidation you were aiming for.

## Sources

Consolidated across the four topic documents in this directory. Philosophy-layer sources:

- "Aliases sparingly" / atrophy — <https://nerdology.org/2021/02/why-i-use-shell-aliases-sparingly/>
- Self-documenting config pattern — <https://gist.github.com/prwhite/8168133> · fzf alias picker <https://github.com/junegunn/fzf/discussions/2982>
- One-tool-per-job / minimalism — <https://news.ycombinator.com/item?id=27992073>
- Snippet capture (pet) — <https://github.com/knqyf263/pet> · executable markdown (runme) <https://runme.dev/>
- topalias (prune via history) — <https://github.com/meteoritt/topalias>
