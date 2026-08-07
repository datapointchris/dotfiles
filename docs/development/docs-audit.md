# Docs Audit Record

A dated record of the 2026-08-06 documentation audit: what was found wrong, and
the measurements to compare against next time.

**This page is a snapshot, not a description of the current docs.** It does not
go stale, because it is a record of one date. Do not "update" it — add the next
audit below the current one. It is the one place in `docs/` where enumerations
and counts are the content rather than a liability.

## Why this exists

The audit was triggered by a small change (the since-removed `shell/` role
overlay) forcing edits to four separate pages. Two of those edits added real reasoning; two were pure
list-maintenance, restating file enumerations that `symlinks/core.py` and
`.zshrc` already declare. The question was whether that ratio held across the
whole of `docs/` — it did, and worse.

The point of recording it is the test Chris named: **if the same pages are stale
again at the next audit, and nothing consulted them in between, they are not
worth keeping.**

## The test for next time

A doc that gets read gets corrected when it is wrong. So **staleness at the next
audit is direct evidence of non-use** — nobody hit the page, tried to follow it,
and found it lying. There is no read telemetry, and this is the closest usable
proxy.

Per page, ask in order:

1. **Is it stale again?** Re-verify the claims in the table below. They were all
   true on 2026-08-06.
2. **If yes, did anything consult it?** Look at what its commits since then were
   *for*. A commit that adds reasoning is evidence of use. A commit that only
   drags the page along behind a code change is pure cost.
3. **If stale and only ever dragged along — delete it.** It has now failed twice.

Re-measure with:

```sh
# Size, against the baseline below
fd -e md . docs/ -x cat | wc -l
fd -e md . docs/ | wc -l

# Maintenance cost per page, highest first
git log --since="12 months ago" --name-only --pretty=format: -- docs/ \
  | rg -v '^$' | sort | uniq -c | sort -rn | head -20

# Dead file references, including inside markdown
refcheck

# Broken nav and internal links
uv run mkdocs build --strict
```

## Baseline (2026-08-06)

| Measure | Before | After |
| --- | --- | --- |
| Lines in `docs/` | 12,058 | 5,656 |
| Files | 81 | 54 |
| `docs/learnings/` files | 35 | 22 |
| Files deleted or relocated | — | 30 |

**Cost of what was deleted: 140 commits in the preceding 12 months** spent
maintaining the 30 pages that turned out to be worth nothing — roughly a commit
every two and a half days. That is the number to weigh against "it's only a
small doc edit."

The three highest-churn pages that *survived* — `apps/menu.md` (37 commits, and
it left with the menu suite in August 2026, which is what that churn was telling us),
`architecture/index.md` (34), `architecture/package-management.md` (32) — are
the ones to watch. High churn on a page that keeps earning its place is fine;
high churn on one that keeps being wrong is the signal.

## What actually went wrong

Five failure modes, in rough order of how much damage they did.

**1. Enumerations that duplicate a machine-readable source.** Roughly 40% of the
corpus. Every one had drifted. This is the category the CLAUDE.md rule now
forbids.

**2. Docs that were confidently wrong, not merely incomplete.** Worse than
absent docs, because following them wastes time and erodes trust in the rest.
Commands that do not exist, paths no code uses, functions never written.

**3. The same subject documented in several places, disagreeing.** Three pages
described the shell libraries and only one was right. Two described PATH and
neither matched `.zshenv`. Two compared the backup tools to each other. A reader
cannot tell which copy is authoritative, and an editor updates one.

**4. Content that was never about this repo.** 1,252 lines — an AWS Glue guide
mentioning dotfiles once decoratively, and a Hyprland survey sourced from the
upstream wiki. `docs/research/index.md` already stated the rule they broke.

**5. Unfalsifiable filler.** "Easy Maintenance", "Experience makes this clear",
"10x faster debugging", "6x faster". Invented metrics and adjectives that
survive any code change because they never said anything checkable.

## Specific claims that were wrong

All verified against the code on 2026-08-06. Re-checking these is the cheapest
way to start the next audit.

| Page | The claim | Reality |
| --- | --- | --- |
| `index.md`, `platforms/tools.md` | `theme preview`, `toolbox random` | Neither verb exists — `theme change`, `toolbox remind` |
| `index.md` | WSL/Arch need ZDOTDIR set by hand | `install.sh` has done it on every platform since `ensure_zdotdir_in_system_zshenv` |
| `index.md` | `configs/`, `apps/`, `shell/` carry the same platform set | None of the three do; `shell/` also had a role overlay (since removed) and `windows/` |
| `architecture/error-handling.md` | Library is at `install/common/lib/error-handling.sh` (×4) | It is `configs/common/.local/shell/`; **zero** code used the documented path |
| `architecture/error-handling.md` | `exit_with_error()` | The function is `exit_error` |
| `architecture/error-handling.md` | Library sets `set -euo pipefail` | Contradicted its own prose 15 lines above; libraries must not |
| `architecture/error-handling.md` | "All 16 GitHub release installers" | 23 |
| `development/shell-formatting.md` | `fatal()`, `require_command()` | Neither exists anywhere in the repo |
| `architecture/shell-libraries.md` | "three system-wide shell libraries" | Documented four; `formatting.sh` table listed ~31 of 49 functions |
| `architecture/github-release-installer.md` | "7 focused functions" | 14 |
| `platforms/packages.md` | `lazygit`, `yazi`, `neovim`, `fzf` install via snap/cargo/system | All four are `github_releases` — 4 of 18 rows wrong |
| `platforms/commands.md` | `~/.local/bin` is last in PATH | It is second; `/opt/homebrew` and fnm absent entirely |
| `tools/hooks.md` | `pre-commit install --hook-type post-commit` | Matches nothing, and omits the registered `prepare-commit-msg` |
| `tools/tasks.md` | 16 tasks | 22 — missing `doctor`, `update`, `link`, `relink` |
| `apps/notes.md` | `notes journal` (×2), interactive menu on bare `notes` | Dispatch handles only `search`/`new`/`recent`/`browse` |
| `apps/notes.md` | Notebook is git-tracked, iCloud-synced at `~/Documents/notes` | Not a repo, Syncthing-synced, that path does not exist, layout differs entirely |
| `apps/index.md` | Safekeep lives here | It moved to its own repo; `Workflows` and `Work Monitor` were omitted despite having pages |
| `tools/symlinks.md` | Per-platform exclusion mechanism | No such code — invented feature. Listed 5 of 18 exclusion patterns |
| `support/corporate.md` | `pip install --user` for language servers | Repo installs via uv; page never mentioned `install/offline/` or the bundle flags, the machinery that actually exists |
| `tests/README.md` | `tests/install/utils/...`, `arch-docker.sh` | `tests/install/verification/...`, `archlinux-docker.sh` |

## Two tests that were passing without testing anything

Found while verifying the docs, and worth re-checking directly — a green test
asserting nothing is the same class of problem as a doc nobody reads.

- `library-flag-pollution.bats` listed `install/common/lib/platform-detection.sh`,
  which has never existed. The probe runs without `-e` by design, so a missing
  library sources to an error, continues, adds no flag, and passes. It reported
  seven libraries covered and checked six.
- `windows-shell-sync.bats` inherited `MACHINE_ROLE` from the developer's shell,
  so the role-overlay test failed on personal machines and passed everywhere
  else — the reverse of what a role test should do. (The role axis was later
  removed outright; the overlay test now builds its own fixture instead of
  reading one out of the repo.)

Both now fail loudly instead. The general lesson: a test whose setup can silently
no-op needs an assertion that the setup happened.

## refcheck was certifying the rot

`refcheck docs/` reported "All file references valid" while five `source` lines
in `docs/` named `install/common/lib/error-handling.sh` — a path no code has
ever used. `check_source_statements` and `check_script_references` globbed
`**/*.sh`, so markdown was never read.

It now reads prose, which is why `refcheck` is in the re-measure list above. Two
limits are worth knowing for the next audit:

- **It validates `source` and `bash` targets, not paths mentioned in prose.**
  Three dead paths in the surviving learnings had to be found by hand, because
  they appear as prose and inside a Taskfile snippet.
- **It cannot tell a citation from a use.** Writing a broken path as an example —
  as this page does — trips it. Describe the path instead of reproducing the
  line that names it.

## What survived, and why

The positive control. These needed no correction, and the reason is the same in
every case: they spend their lines on decisions and cite code rather than
reproducing it.

- `configuration/docker.md` — the WSL two-engines problem, the `/usr/bin/docker`
  stub, why not Docker Desktop
- `architecture/tmux-sessions.md` — every claim carries its reversal condition
  ("Two attempts at this have been built and reverted. Do not rebuild either
  without reading why")
- `architecture/management-interface.md` — a decision reversed, with the original
  reasoning quoted and the two capabilities that turned out missing
- `apps/work-monitor.md` — hardware and algorithm choices
  that cannot be derived from `--help`
- `reference/rebuilding-a-machine.md` — documents what the automation *cannot* do,
  which is by definition not in the code

The shared property: **nothing in them changes when code changes.** That is the
test worth applying to a new page before writing it.

## A note on method

The audit ran three parallel agents over separate parts of `docs/`, each
required to verify claims against the code rather than judge on reading. That
mattered — one agent reported `borders` as absent from `packages.yml`, and it is
present at line 538 with its tap declared. **Spot-check agent findings before
acting on them**; roughly one claim in twenty was wrong, always in the direction
of over-reporting.
