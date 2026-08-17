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
list-maintenance, restating file enumerations that `src/dotfiles/symlinks/core.py` and
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

---

## Second pass: 2026-08-08

Not a full audit. This was the docs half of step 9 of the Python conversion, so
its scope was narrower and its trigger different: two structural changes had
landed since the first audit — `PLATFORM` split into six machine coordinates, and
bats was deleted — and the question was which pages had been left describing the
old shape.

### Baseline

| Measure | 2026-08-06 (after) | 2026-08-08 |
| --- | --- | --- |
| Lines in `docs/` | 5,656 | 5,617 |
| Files | 54 | 56 |
| `docs/learnings/` files | 22 | 22 |

Two pages added (`system-configuration.md`, `observability.md`) against a small
net reduction in lines, which is the ratio to want.

### What the first audit's test said

**Staleness at the next audit is direct evidence of non-use.** Applied to the
three pages the first audit named as highest-churn-but-surviving:

- `architecture/index.md` — **stale**, and its commits since were mostly dragging
  it behind code changes. Its shell-source section still described
  `source "$SHELL_DIR/$PLATFORM.sh"`, two structural revisions out of date. Kept
  rather than deleted, because the sections around it carry real reasoning and
  the page is the entry point the sidebar puts first — but it is now the page to
  watch, not `package-management.md`.
- `architecture/package-management.md` — **not stale**. Highest churn of any
  surviving page and correct throughout; the churn is the subject moving, which
  is the healthy case.
- `apps/menu.md` — gone with the menu suite, as the first audit predicted.

### What was found

Every one is the same failure mode: **a page describing a shape the code no
longer has**, none of them caught by `refcheck` or `mkdocs --strict` because the
paths and links were all valid.

| Page | The claim | Reality |
| --- | --- | --- |
| `architecture/index.md` | `.zshrc` sources `$SHELL_DIR/$PLATFORM.sh` | It loops over six `DOTFILES_*` overlay directories |
| `architecture/index.md` | `shell/{platform}/{platform}.sh` (macos, arch, wsl, linux, windows) | `shell/<axis>/<value>/`, and most axes have no directory at all |
| `architecture/index.md` | "Deep Dives" card grid | Named 2 of 9 architecture pages; wrong since the third was added |
| `index.md` | "platform-specific overrides", "Platform is the only axis" | Six axes since the split |
| `learnings/app-installation-patterns.md` | `apps/{platform}/`, with a `create_symlinks` call | Neither the layout nor the function exists |
| `reference/tools/tasks.md` | Both front doors call `install/ops/` | They reach `src/dotfiles/`; `ops/` holds one script |
| `reference/tools/symlinks.md` | "Only the resolved platform's overlay file is linked" | The coordinate overlays, keeping their axis path |
| `architecture/management-interface.md` | Group→Contents table | `--list` prints it, and it had drifted |
| `index.md` | `menu <term>` | Left with the menu suite; it is `doit find` |
| `development/testing.md` | Three test layers, two of them bats | One runner |

Two were code rather than docs, found by writing the page that would have had to
describe them: `bridge.ops()` had no callers, and `check --json` emitted a bare
array where `status.json` held a versioned document — two shapes for one answer,
both crossing machines.

### What did not need correcting

Verified rather than assumed this time, since the first audit's finding was that
roughly one agent claim in twenty was wrong:

- **Every app verb the docs name exists.** `theme change/apply/update/list`,
  `font apply/update/install`, `toolbox list/show/remind/check`, `notes journal`
  — all checked against `--help`. `notes journal` was wrong at the first audit
  and has since been fixed.
- **Every `dotfiles` verb the docs name exists**, checked the same way.
- `reference/platforms/tools.md`, `configuration/docker.md`,
  `architecture/tmux-sessions.md` — untouched and still correct. All three spend
  their lines on decisions.

### The lesson this pass adds

The first audit's rule was *do not enumerate what a command prints*. This pass
found the harder case: **a page that describes a mechanism rather than a list,
and the mechanism changes.** No enumeration rule catches
`source "$SHELL_DIR/$PLATFORM.sh"` — it is prose about how something works, which
is exactly what a doc is supposed to contain.

What catches it is treating a structural change as a docs change. `refcheck`
finds a moved file and `mkdocs --strict` finds a broken link, but nothing
mechanical finds a page still describing the design you just replaced. The
practical version: after landing a change that alters a *shape* — a layout, a
lookup, a dispatch — grep `docs/` for the old vocabulary before the commit, not
at the next audit. `PLATFORM` was one grep away for two days.

---

## Third pass: 2026-08-17

A full audit, and the trigger was cost rather than staleness.
`architecture/management-interface.md` took 57 commits in 31 days and 1333 lines
of churn against a 565-line file. Chris named the standard it was failing: a doc
is no good if it has to change on every commit.

### Baseline

| Measure | 2026-08-08 | 2026-08-17 (before) | After |
| --- | --- | --- | --- |
| Lines in `docs/` | 5,617 | 8,015 | 4,537 |
| Files | 56 | 64 | 53 |
| `docs/learnings/` files | 22 | 29 | 21 |
| Shingle score, whole corpus | — | 3,174 across nine pages | 470 across all 53 |

The corpus grew 43% in nine days. Every page added in that window described a
subsystem that had just been written, which is the condition this pass is about.

### The sixth failure mode, and the measurement that finds it

**A page that restates a module docstring.** The first audit's rule catches an
enumeration. The second's catches a mechanism whose shape changed. Neither
catches prose that is *correct*, is *about a mechanism*, and already exists
fifteen lines into the module it describes. Both copies then have to be edited,
and only one of them is next to the code.

It is measurable. Count six-word runs a page shares with any docstring under
`src/dotfiles/`:

```python
import re, pathlib
def shingles(text, n=6):
    words = re.findall(r"[a-z_`.\-/]+", text.lower())
    return {' '.join(words[i:i+n]) for i in range(max(0, len(words)-n))}
src = shingles(' '.join(p.read_text() for p in pathlib.Path('src/dotfiles').rglob('*.py')))
for f in sorted(pathlib.Path('docs').rglob('*.md')):
    print(len(shingles(f.read_text()) & src), f)
```

The scale separates cleanly, and the ends of it were known before the number was
computed. `configuration/docker.md` scored 1, `architecture/tmux-sessions.md` 1,
`reference/tools/tasks.md` 0 — the three pages the earlier audits named as
surviving because nothing in them changes when code changes.
`architecture/github-releases.md` scored 613 over 390 lines,
`offline-bundles.md` 557, `observability.md` 549, `management-interface.md` 529.
A score in the hundreds means the page is a second copy of the code's own words.

It took three passes to clear, and the second and third are the finding. A page
handed a cut list came back half its length with its score barely moved —
`system-configuration.md` went 300 lines to 296 and 301 to 293. Re-measuring is
what caught it; reading the diff would not have. **A page is not done because it
is shorter.** Run the count again and cut until it drops: those two finished at
0 and 8, and `offline-bundles.md` and `github-releases.md` at 1 and 2 after a
third pass. The highest score left in the corpus is 86.

**The fix is not deletion.** A decision belongs in both places when the constraint
is one an editor must meet, which `standards/documentation.md` § "Document a
constraint at the edit site" requires. What comes out is the *mechanism* — the
walkthrough, the per-field account, the measurements — replaced by one sentence
naming the module. `architecture/custom-installers.md` is the model: 162 lines to
48, holding the routing test and three rejected protocols, with
`src/dotfiles/providers/custom.py` named for the rest.

### What the second pass's test said

`architecture/index.md` was named the page to watch. It was stale again, and
three of its claims were false: a manifest example declaring `function_groups:`
and `alias_groups:`, which `rg -uu` finds nowhere in the repo; a `npm_globals:`
list triggering nvm, retired in favour of fnm; and an optional per-platform
Neovim config layer that has never existed. That is failure twice, and the test
says delete.

It was rewritten instead, and the reason is the one the test does not cover: the
page carries reasoning that exists nowhere else — the WSL-to-Windows bridge and
why it refused to delete, the `MACHINE_ROLE` axis tried and removed, the
mechanism-versus-values test with the `update-tldr` case that sat on the wrong
side of it for months, and the four-level git identity chain. The stale half was
enumeration; the durable half was decisions. **A page that is both gets cut in
half, not deleted** — and if the enumerations grow back by the next audit, the
test applies without an exemption.

### What left the repo

Eight pages moved to where their subject actually lives, which is the half of
this pass that reduces future churn rather than current lines.

- **Six to the hub** (`~/docs`): the libpcre2 symbol warning, stdin consumption
  in `while read` loops, TTY detection inside command substitution, man page
  overstrike, and font/terminal metadata. None named anything in this repo.
- **One split**: the USB DAC note. The diagnosis is general and went to the hub;
  the WirePlumber drop-in this repo deploys stayed.
- **Two to the fleet standards**: the failure-registry lesson became
  `cli-design.md` § "A value the caller needs back is returned, never parsed back
  out of a stream", and the bootstrap-dependency lesson became `testing.md` §
  "An end-to-end environment is the production image, not an approximation of
  it". Both are rules every repo can break; neither was about dotfiles.
- **`architecture/tool-composition.md` was deleted rather than moved.** Its
  central claim — never build the picker in, compose at the shell — is a
  position the fleet has since reversed. `cli-design.md` § "The interactive
  picker is `choose`, and it is never `apply`" names `theme choose` and
  `doit labs choose` as the shape. A page can go stale by being overtaken rather
  than by being wrong about its own repo, and nothing mechanical finds that
  either.

### The test for next time

Everything the first two passes said, plus: **run the shingle count before
reading anything.** It ranks the corpus by the failure mode that costs the most
and it takes seconds. A page scoring in the hundreds is a rewrite candidate
before anyone has read a line of it.

One thing this pass did not fix. The lesson in
`learnings/cargo-binstall-needs-release-binaries.md` generalises — the install
method is decided by what upstream publishes, not by what the tool is written in
— and no standards file covers install-method selection. `dependencies.md` holds
three rules and all three are about trust. Placing it means broadening that file
or adding one, which is a decision about the fleet's own surface rather than
about these docs.
