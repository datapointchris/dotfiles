# Management Interface

How you drive this repository: a `dotfiles` CLI that works from anywhere, a `task`
front door for work inside the repo, and one shared implementation underneath both.

## Layering

Two front doors sit over the same implementation, so neither can drift from the other:

```text
dotfiles <noun> <verb>       task <verb>
             \                  /
              src/dotfiles/            the package: the stage walk, symlinks, catalog
              install/common/*         the per-tool installer scripts still in bash
```

`src/dotfiles/bridge.py` is the seam. Every function in it reaches bash that has not
moved yet, which makes the remaining conversion work countable: when a resource gains a
real implementation, its entry disappears, and the module goes with the last one.

`task` keeps what belongs to working *in* the repo rather than on the machine — the test
suite and the docs site — and calls them directly. Anything that is already one command
gets no wrapper.

## The `dotfiles` CLI

`src/dotfiles/`, installed by `uv tool install` and so on `PATH` from any directory.

The grammar is **noun-verb with three reconcile verbs**, Terraform-shaped. `plan` reports
what `apply` would change and never writes; `apply` makes it so; `check` reports what is
*wrong*, which is a different question. All three sit at the top level and again under
each resource, so narrowing to one part of the machine is the same sentence with a noun
in it. `dotfiles --help` lists the nouns.

`plan` is `apply` minus the last step — structurally the same walk — which is why there
is no `--dry-run` for `apply` to be the opposite of.

**Why `check` is not just `plan` with a different name.** A package a version behind is
drift: expected, benign, and exactly what `apply` is for. A machine-local value nobody
set, a file only safekeep can restore, a declaration that will not validate, a checker
that crashed — those need a person. One verb answering both meant one exit code carrying
both, and the scheduled unit sat permanently `failed` on a machine whose only fault was
being a version behind. The distinction was already in the data: `Repair` says who can
fix a change, and `plan` keeps what `apply` can while `check` keeps what it cannot.

So `plan` exits 1 when changes are pending (`terraform plan -detailed-exitcode`) and
`check` exits 3 when something is wrong and never 1. The periodic timer runs `check`,
and the shell nudge — which has always fired on Issues only — is now reading the verb
that means it.

### One section per resource, and a closing line naming the verb

The split above is right and was invisible on screen, which made both verbs read as
broken. A machine whose only fault was four logged-out CLIs printed nine converged rows
under `plan` — correct, and indistinguishable from a run that had failed to look. The
same machine under `check` printed the four findings *above* every verdict row, because
the fold rendered each item as it decided it and the verdicts came afterwards: `auth`'s
rows landed under the progress line for `credentials`, and `credentials` then reported
converged two lines below them.

Three things fix it, and none of them changes what is measured.

Each resource is folded and printed the moment its measurement lands, as a **section** —
the resource's name, what it found, and the rows that finding is made of, with a blank
line after it. The progress line above it is **retracted** rather than left on screen, so
the report is one list of resources rather than two. And a group of few enough items
**names them** instead of counting them: `go, node, rust, uv` is a list crammed into prose
that drops the version of each, and `~/.env matches the manifest` withholds the whole of
what the file says this machine is. `output.LISTED_MAX` is the bound, above which `-v` is
what expands the count — which leaves the declared inventories as counts, where their own
`list` verb is the better door anyway.

**The bound is per group, not per resource.** `system` measures a hundred declared
packages and nine `system.yml` rows and says so in two sentences, because they are two
questions; one threshold over the whole resource could only answer by suppressing both.
A resource that measures one kind of thing declares no group and is weighed whole.

**The name is the heading, and `converged` is said once.** The left column spelled the
verdict on every section, so a healthy run was that word nine deep in the one position a
reader scans for the name of the thing. It is a mark now — and a mark rather than colour
alone, because `NO_COLOR` is a preference this fleet honours and a report carrying its
verdict only in an escape code answers nothing on a machine that asked for none.

The closing line is where the word goes, since the run's verdict is about the run rather
than about each part of it. It also says which question was answered and where the other
one is asked, which is the answer to "plan converged and said nothing — am I using it
wrong":

```text
converged nothing for apply to change; 5 item(s) need a person — run: dotfiles check
issue     2 resource(s) need a person: packages, auth
```

Each verb's row also words the *other* verb's count as that verb owns it. A `plan` row
reading `converged` beside `4 need attention` was a row contradicting itself, and both
halves were true — apply has nothing to do here, and four tools are logged out. It reads
`4 need a person` now. The mirror case is a `check` row reading `converged` beside a
non-zero count, which is a declared package merely absent, so it reads `3 differ`. Neither
verb ever restates its own answer as a count beside the sentence that already gave it.

**`apply` closes in the same grammar.** It measures in sections, acts in sections, names
the two sets it walks past as sections, and closes on the same `{verdict} {sentence}` the
read verbs do — carrying what changed, what needs a person, what nothing could measure,
and the verb that owns each. A write verb with renderings of its own instead — a
full-width rule naming the machine, a line at column 0 above each group of work, a bare
warning for a resource that refused, a second rule for the verdict — ends the run a
person watches longest in the line of the report that answers least.

**That closing line ends a run that measured something, and only that.** An `apply` that
refuses before the walk — nothing selected, a machine that will not resolve, `--offline`
with no bundle to install from — has no counts to compose one from, so it closes on the
refusal shape every other door in the tool uses: `✗` and the sentence, with the advice
hung under it. Two shapes, one saying what the machine became and one saying why the run
never started, and nothing left in a third. The declaration gate is on the first side: it
measured the declaration, and closes on that row's verdict.

Its whole human report goes to **stderr**, the closing line included, where a read verb
puts its headings on stdout and its evidence on stderr. The split is right for a read —
the heading is the answer, so redirecting separates an answer from a transcript — and
wrong for a write, whose answer is what the machine became. `apply`'s stdout is the run
record, so keeping every line off it means no branch has to remember to fall silent
under `--json` and no refusal can hand a caller a heading where the document should be.

Nothing here reaches `--json`, which is a document rather than a rendering: it carries
the verb, the verdict, the four counts and the items behind each of them, so a caller
parses those rather than the screen. [Observability](observability.md) has its shape.

Bootstrapping a bare machine is `./install.sh --machine NAME`, and its whole job is
getting to this CLI: check `git` and `tar`, stage an offline bundle if one is present,
install uv, `uv tool install --editable`, and print the `plan` and `apply` that converge
the machine. It validates the manifest name itself — the only check in the system that
does — because the CLI that would answer the question does not exist yet.

**It prints those two rather than running one, and that is deliberate.** It ended in
`exec dotfiles apply` until a bare `./install.sh` on a WSL box whose `~/.env` already
named it went straight into a half-hour networked run nobody had asked to start, and sat
on a blocked cargo download behind the work firewall. Getting the CLI onto a machine
answers "can this box run any of this at all", and converging it answers "what should
this box become" — one is cheap and always right, the other is long and worth planning
first. Fusing them meant the cheap question could not be asked on its own, and the
expensive one could not be declined. `--offline` stays on the bootstrap because it
decides where uv and the wheels come from, which is settled before any CLI exists to be
told; `--through` left with the `exec`, since the run it capped is now typed directly.

## `dotfiles update` — the checkout is the installation

`update` means here what it means for every other tool in the fleet: update this tool.
The verb once pointed at the machine, which is what `apply` covers now, and the entry
that sanctioned the divergence in `cli-design.md` was deleted when it stopped being one.

It pulls `--ff-only` and then repairs the two things a pull can invalidate. Deployed
files that moved leave the machine linked to paths that no longer exist, so the symlinks
are rebuilt. A changed `pyproject.toml` or `uv.lock` leaves the tool venv resolved
against the old dependency set, so it is reinstalled — and that is the exact bound on
when an editable install goes stale, because uv points at the working tree, so code
changes *are* the new code and never need a rebuild. The reinstall is last and the
process ends with `os._exit`: `--reinstall` replaces the virtualenv the running
interpreter lives in, so anything imported after it reads files that are gone.

**`pyselfupdate` is deliberately not used, and its refusal is correct rather than a
gap.** It declines to reinstall over a `directory`/`path`/`editable` requirement, and
that is the right answer: this repo publishes no releases, its source of truth is the
working tree, and installing a release over it would destroy the thing being updated.
Nothing should be filed to add releases here on the strength of it.

For the same reason there is no update *notice* — there is no published version to
compare against. Both read-only verbs end with the honest equivalent: where the checkout
sits against the last-fetched `origin/main`, and how long ago that fetch was. It reads
`.git` and never the network, so it is free at a prompt and correct offline, which is
why it dates its own answer. `dotfiles update --check` is the same line after an
explicit fetch, and exits 1 when there is something to pull.

## The machine environment (`~/.env`)

`~/.env` is the first thing `.zshrc` sources, and where every command that is not given
`--machine` learns which machine it is on. It answers two questions — which machine this is
(`MACHINE`) and which features it wants running (the flags from `install/flags.yml`) —
and it also carries secrets and machine-local values that must never be checked in.

`MACHINE` is the chosen one: it names a manifest, and everything else is derived from that
manifest by the resolver. The coordinates that manifest declares select the `<axis>/<value>`
directories under `configs/`, `shell/` and `apps/`, and none of that reaches this file.
`.zshrc` and `.bashrc` glob the deployed tree instead, because the symlink manager already
put exactly this machine's directories there. Placing this file by hand is therefore the
whole of the pre-install bootstrap: `session.resolve_machine` reads
the file itself when `$MACHINE` is unset, so a rebuild that restores `~/.env` first never
needs `--machine` on anything. Reading the file rather than only the environment is what
makes that work outside a login shell — a scheduled `check` inherits no `~/.env` at all.

It used to be hand-authored, which made it the one piece of setup with no source of
truth: a flag added to the repo reached no existing machine, and nothing could say which
machines had drifted. `NVIM_AI_ENABLED` survived that way for a long time — set
everywhere, read by nothing.

Now `dotfiles env` generates and maintains it, at the first stage of every apply.

Everything above the `# OVERRIDES` marker comes from the manifest and `flags.yml` and is
rewritten on every apply. Everything below it is preserved verbatim, which is what makes
the file safe to regenerate while it holds API tokens. A file with no marker predates
generation, so all of it is treated as hand-written and moved below — lossless by
construction. Syncing also takes a `.bak` and writes through a temp file and a rename,
because a half-written `~/.env` would take a machine's secrets with it.

The bootstrap is genuinely circular — `~/.env` names the manifest, and the manifest
generates `~/.env` — so a bare machine still has one line to type by hand. Only
`MACHINE=` though; the first `dotfiles apply --machine NAME` fills in the rest.

Every generated line is written as `export NAME="${NAME:-value}"`, so the ambient
environment still wins for a single shell — `ZSHRC_DEBUG=1 zsh` and
`MACHINE=other ./install.sh` both keep working without editing the file.

Flags are for behavior that is present and cheap, where the only question is whether this
machine wants it. Payload that is expensive to install stays a manifest tool list, and
config a program discovers by path and cannot branch on (hyprland, waybar, ghostty) stays
a coordinate variant under `configs/`.

### Which gates are flags

A `command -v fzf` guard is not a flag and should not become one: fzf has no reason to be
installed and unwanted. A gate earns a flag only when *installed but off* is a state
worth having — which is the state the old existence-only gates could not express.

The shell plugins qualify because they carry both a preference and a real startup cost;
turning the four off measures at roughly 130ms saved. The manifests use that: the work box
sets `SHELL_NUDGE: false` because the review register is personal, and `linux-lxc-server`
turns off the whole interactive plugin set. The plugins are still *installed* there, so
turning one back on mid-debugging is a `~/.env` edit rather than a reinstall.

Two ordering hazards, both real and both now handled:

- A plugin must be sourced at top level, never from inside a helper function. A function
  scope changes what a plugin's own `typeset` calls do, so the load stays inline and
  slightly repetitive rather than being factored into a `load_plugin` helper.
- `zsh-vi-mode` overwrites the whole keymap, so the arrow-key history search and the
  Claude widgets are bound from its post-init hook. With `SHELL_VI_MODE=false` nothing
  would call that hook, so `apply_shell_keybindings` is a named function with two callers
  — the hook, and the tail of `.zshrc` when the flag is off.

### Beyond the shell

Neovim read the same vocabulary until 2026-08-12 and no longer does. `core/profiles.lua`
derived a `minimal` plugin set from `DOTFILES_CAPACITY == 'server'`, with `NVIM_PROFILE`
as the override. Before the axes split it read `PLATFORM == 'linux'`, which was the right
answer for the wrong reason — `linux` happened to be the one headless platform, so a
graphical Ubuntu desktop would have got the lean set.

Following the coordinate was the correct fix and the profile still did not earn its keep.
Exactly one machine ever reached it, the LXC, and the price was a hand-kept allowlist of
editing essentials maintained forever for one box nobody sits at. Deleting it leaves one
question — whether Neovim is embedded in VSCode — which no coordinate answers, because it
is a fact about the process rather than about the machine.

`plugins/typos.lua` is the counter-example, and worth keeping in mind before reaching for
this vocabulary at all. It was `PLATFORM ~= 'wsl'`, then `MACHINE_ROLE ~= 'work'`, then a
test for `~/notes` — each one a label standing in for a condition that turned out not to
need expressing. It is now an unconditional remote spec: capture is scoped to `notes_root`,
so a machine without one writes nothing, and `setup()` creates no directories. The gate
existed only because a `dir =` local checkout errors on every startup when the directory is
absent, which is a fact about local specs rather than about machines.

`core/options.lua` keeps its check and spells it `WSL_DISTRO_NAME`, which WSL sets
itself. It read `DOTFILES_HOST == 'wsl'` first, on the reasoning that win32yank genuinely
is a fact about the host rather than a stand-in for one — true, and still the wrong
source, because a declared coordinate is a second description of something the runtime
already states and `tmux.conf` was solving the identical problem the direct way three
files over. The test survives the correction and gains a clause: if the condition can be
stated as something the code needs, state that; if the machine already announces it,
read the announcement; reach for a coordinate only when the difference really is which
kind of machine this is, and no process on it says so.

tmux gets nothing. Every conditional in `tmux.conf` is real runtime detection — is this
pane running vim, is `$WSL_DISTRO_NAME` set, does the theme file exist, is tpm cloned —
and none of them is a preference in disguise. A flag with no consumer is how
`NVIM_AI_ENABLED` happened, so the mechanism waits until something needs it.

## Selective installs and updates

There is no phase registry. `dotfiles apply` measures the whole plan once and acts on it
in `Stage` order, so what a run covers is every provider that planned something and what
a run does first is whatever sits at the lowest stage. There were three lists of that
order at the worst of it — `install/phases.sh` for `update.sh`, `apply.REGISTRY` for
`install.sh`, and the `Stage` enum the resolver already sorted on — and the first two are
gone. Keeping a hand-written one is what let `system/manager`, the OS package upgrade,
sit at a stage no phase named and never run at all.

A selector is a resource, or one provider inside one — `dotfiles apply --help` lists
what `--skip` takes and `dotfiles <noun> apply --source` narrows below that. The bash
half had four hand-maintained groups (`system`, `languages`, `tools`, `plugins`) whose
membership was a fifth list to keep in step; a resource and a provider are what the
provider registry already knows, so there is nothing to maintain.

The one group worth its own name was `system`, because it needs sudo and dominates the
runtime. `--skip system` is that, and it is derived rather than declared.

```bash
dotfiles apply                        # everything
dotfiles apply --skip system          # a whole resource: the sudo-gated, slowest part
dotfiles apply --skip plugins/tpm     # one provider inside one, leaving its neighbours
dotfiles packages apply --source cargo_packages   # one section, and what it needs
dotfiles apply --owner datapointchris # only tools traceable to that owner
dotfiles apply --package lazygit      # one declared entry, and what it needs
dotfiles apply --through system_upgrade           # stop after that stage
```

Every selector reads as well as it writes. `plan` answers "what would `apply` change", so
a scope the write accepts and the read cannot express is not a narrower preview but no
preview at all — for a while `apply` could be narrowed to one section and there was no way
to rehearse it, which is the case a preview is worth most in. What stays write-only is
what describes *how* to write rather than what to cover: installing from a staged bundle,
or forcing an entry past what measuring concluded. `tests/cli/test_conformance.py` asserts
the split across the whole tree, because the gap opened by adding a selector to one verb
and forgetting its sibling, and nothing else notices.

### Scope and force are different flags

`--reinstall` used to take an entry name, which made one flag answer both questions:
`--reinstall lazygit` said *what* to cover and *that* measuring should be overruled, so
the scope it carried existed nowhere else and no other resource could honour the force.
It is two flags now. `--package` is the narrowing, one row below `--source` and reaching
every resource; `--reinstall` is a boolean over whatever the narrowings left, which any
resource's `diff` can read.

Bare, `--reinstall` therefore means everything the run covers. That is expensive and not
dangerous — a fresh `go install` of every Go tool and a re-download of every release —
which is the case `cli-design.md` § "Scope is structural: the argument's presence selects
it, never a flag" sanctions a set-wide act for. Repairing one tool is
`--reinstall --package <name>`, and the two compose because they answer different
questions.

A `--package` name is measured against the `Selection` the walk will use, not against the
machine's whole plan. `packages apply --package uv` names the toolchain, which that noun
does not reach, and is a usage error naming the address that does carry it — where
validating against the plan accepted the name, walked past the item, and reported a
converged machine to a caller who had asked for work.

`--through` is the one selector that is not a selection of parts. `--skip` and the
resource sub-apps say *which mechanisms*; neither can say *how far*, because the stages a
resource's providers sit at are spread across the run — expressing "the system half and
no further" as `--skip` means knowing which providers live below the line, which is the
registry's knowledge and not a caller's. It is a ceiling on the ordering, carried on the
`Selection` beside the provider narrowing so the two intersect, and the e2e base images
are built with it.

A section brings what it declares it needs. `--source cargo_packages` on a machine
without rustup installs the Rust toolchain first, because `needed_by` already says the
runtime is wanted *because* that section resolved; narrowing to the section alone honoured
the declaration in the plan and ignored it in the run, and failed with
`cargo: No such file or directory`. `--package ripgrep` answers the same way and through
the same registry relation, so one entry brings its runtime and no other.

Owner narrowing drops every provider whose contents cannot be traced to a GitHub owner,
and then every resource left holding none — so `symlinks`, `env`, `identity`, `auth` and
`credentials`, which have no provider to be ownable, fall out of the walk rather than
deploying in full alongside somebody's tools. Ownership is derived from
whichever field carries it — `repo`, `github_repo`, or a Go import path in `package` —
not from a `personal` tag, because a tag has to be remembered on every new tool and
silently excludes whatever it misses.

`dotfiles apply --owner` is the command that matters most in practice: a newly released
personal tool has to be installed before any self-updater can maintain it, and those
tools span four sections (`go_tools`, `github_releases`, `custom_installers`,
`git_uv_tools`), so owner is the only selector that reaches all of them at once.

An address is `resource` or `resource/provider`, and one naming neither is a usage error
rather than an empty selection. A run that accepted a misspelt `--skip` would install the
sudo-gated stage the caller was avoiding and report success — which is also why a trailing
`plugins/` is refused instead of read as the bare resource.

Skipping a provider leaves its resource in the walk with that provider removed, and the
narrowing is structural: the resource is handed a plan that does not contain what it was
told to leave alone, so it cannot observe it, diff it or act on it. It is applied per
resource rather than once for the whole walk, so a `--skip` aimed at one resource cannot
change what another one sees. The case that proved it: `toolchains` derived the Go runtime
by finding `go_tools` items, so a globally narrowed plan made `--skip packages/go` stop
planning a runtime the caller never named. That derivation is a provider's now and happens
at resolve time, before a selection exists.

Narrowing is the resolver's: `--owner` produces a plan containing only that owner's
entries, and `Plan.providers` says which stages have anything left to do. It was a
hand-rolled filter block per installer script before that, and only the Go one honoured
the owner — so `--mine` ran cargo, uv and npm in full while claiming to filter.

### Install and update are one act

There is no update verb. `apply` installs what is missing and reinstalls what differs
from the newest release, and which of those a given row needs is the verdict's answer
rather than the caller's.

*Differs*, not *is behind*. A version above the newest release is drift too — nothing
upstream publishes it, so no install anything here performs would produce it. That is
the state a repo leaves behind when it re-versions downwards, and reading it as
comfortably current is how a machine kept a stranded `ifiles` 2.10 long after the
verbs it called had been renamed. The comparison is only made against a figure
measured this run, because against a *cached* one the same reading means the opposite:
the tool self-updated and the cache has not caught up.

That line used to be drawn by accident rather than intent. `go install @latest`, `cargo
binstall` and the release installers all create as a side effect of upgrading, while `uv
tool upgrade` and `<tool> update` cannot — so whether an update installed a newly
declared tool came down to which section of `packages.yml` it had been added to. A
`MISSING` row and a `STALE` row are now different verdicts with different repairs, and
both are reported before either is acted on.

`dotfiles packages check` answers the same question on demand. It is deliberately
separate from `dotfiles machines check`, which runs on every commit: that one compares
`packages.yml` against the manifests and what can install them, and a machine part-way
through a rollout is not a repo defect that should fail a commit.

### What a provider is allowed to claim

A per-tool line must be derived from observed state: a version or ref that changed, or a
non-zero exit. It may never be derived from "the command returned", because
`uv tool upgrade`, `cargo binstall`, `npm update -g`, and `git pull --quiet` all exit 0
whether or not anything changed.

The `Change` is what supplies that now. A row is planned because it was measured as
missing or behind, and its `Outcome` names what was repaired — where the bash snapshotted
installed versions either side of every command to work out the same thing afterwards.
The one place the snapshot survives is `clone.pull`, which reports the commit either side
because `git pull --quiet` on a current clone prints nothing at all.

Where a tool already reports its own outcome accurately, the installer delegates instead
of re-deriving one. `theme.sh --update` and `font.sh --update` run `theme update` /
`font update`, let their output through, and propagate the exit code. The earlier
version matched a sentinel string against their output and always missed, printing
`theme updated` on every run; it also ended in an unconditional `exit 0`, so a genuine
failure never reached the report.

## Logins, which are checked and never repaired

A converged machine is not necessarily a working one. Every binary can be installed,
every symlink deployed and every flag set while the CLIs that do the work sit logged out
— which was the state of the Arch box on 2026-08-12, with `learning`, `meso`, `nomad`
and `atuin` all unauthenticated and `dotfiles check` reporting a screen of converged
rows. The `auth` resource closes that gap, and four decisions inside it are worth
stating because the code cannot state them about itself.

**The manifest names which tools, the module says how each is asked.** A machine's
`auth:` list is the roster and `src/dotfiles/resources/auth.py` holds one probe per name,
with a test asserting the two sets match in both directions. That is the split
`custom_installers` and `steps` already use, and it is forced harder here: `aws` arrives
through a custom installer and `bbkt` is installed by hand on the work box, so a field on
a `packages.yml` row could not reach either of them. Putting the roster in code instead
would be the one place this repo keeps a machine's declaration out of.

**Every probe is local, and each one carries the measurement that picked it.** `check`
runs unattended on the timer `src/dotfiles/providers/schedule.py` installs, so a network
round trip per declared tool is unaffordable and would report a working login as broken
on any machine that is offline — with nobody at the desk to discount it. The nudge is not
a second caller: it prints a line a previous run left in a file, which is why it costs a
shell prompt nothing. The cheap probe is per tool and
it inverts between them, which is the part worth writing down: `gh auth token` is 30ms
where `gh auth status` validates against the API at 333ms, while for the personal data
CLIs `auth status` is the 4ms one — it reads the keychain and makes no HTTP call — and
`auth token` refreshes at 215ms. `atuin` and `aws` have no cheap CLI probe at all and are
answered by a file, because `atuin status` queries the sync server once a session exists
and `aws sts get-caller-identity` is 698ms and networked.

**Nothing is ever repaired, and `apply` cannot reach it.** A login is a browser flow, a
password or a device code, so every finding is `Repair.BY_HAND` and therefore never
`actionable` — which is what keeps it out of the stage-ordered walk entirely rather than
relying on a branch that could be wrong. Getting this backwards would turn every `apply`
on a headless box into a prompt storm. It is the same answer `identity` gives for the
same reason, and both resources have a `check` and no `apply`.

**Whether a credential is still current is out of scope, deliberately.** An expired
keychain token and a stale SSO cache both read as present. Asking properly means a round
trip in every case, which is the one thing this resource cannot do. `<tool> auth status
--json` already carries an `expired` field, so that is where a later pass starts.

## Why there is a CLI now

A standalone `dotfiles` CLI was considered in July 2026 and deliberately not built, on
the grounds that it would "only re-wrap existing scripts for a cosmetic rename —
maintenance cost with no capability gain." That reasoning was later reversed, because
two capabilities turned out to be missing rather than merely renamed:

**`task` cannot run from outside the repository.** Task discovers `Taskfile.yml` by
walking up from the working directory, so every management action was gated behind a
`cd`. This is structural, not cosmetic — no amount of Taskfile work fixes it.

**`update.sh` had no argument surface at all.** Its final line was a bare `main`, so
there was no way to skip the sudo-gated system phase or to refresh only your own tools.
Selective update did not exist anywhere in the repository. It gained one, and then went
entirely: `apply` is the update, and `--skip` is the selector.

It was bash in this repository, on the grounds that a separately-distributed binary
could never function on its own — the CLI's job is invoking scripts that exist only
inside the cloned repo. That constraint is real and unchanged; what changed is that
`uv tool install --editable` satisfies it. The installed tool *is* the checkout, so
there is no distribution channel to buy and nothing to keep in sync, and the CLI gets a
real type system, a test suite, and dependencies it can declare.

## Ownership

| Concern | Owner |
| --- | --- |
| Machine bootstrap | `install.sh` — POSIX sh, up to the point uv installs the CLI |
| Installing | `src/dotfiles/reconcile.py` — `apply_machine`, beside the two read verbs |
| Updating the machine | `dotfiles apply` — one verb; a behind package is a `STALE` row |
| Updating this installation | `src/dotfiles/commands/manage.py` — pull, relink, rebuild the venv |
| Where the checkout sits | `src/dotfiles/checkout.py` — read from `.git`, never the network |
| Package query narrowing | `src/dotfiles/resolve.py` — the plan is narrowed before a provider sees it |
| Symlink management | `src/dotfiles/resources/symlinks.py`, primitives in `symlinks/core.py` |
| Package declarations | `src/dotfiles/catalog.py` — one typed row per entry; a section's schema is its dataclass |
| Declaration drift | `dotfiles machines check` — packages.yml vs manifests vs installers |
| Machine drift | `dotfiles plan` — this machine vs what its manifest declares |
| What this tool's own config resolved to | `dotfiles config show` — the value and the rung that supplied it |
| Tool discovery | `toolbox` (across all installed tools) |
| Cross-repo operations | `forge` |

The `apps/` scripts (`notes`, `packup`, `patterns`, …) remain **independent
user tools** with their own identity and `toolbox` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.
