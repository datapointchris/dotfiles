# Management Interface

Drive this repository through the `dotfiles` CLI, which works from any directory.
`task` is the second front door and keeps what belongs to working *in* the repo —
the test suite and the docs site. Anything already one command gets no wrapper.
Both doors reach one implementation in `src/dotfiles/`. The grammar is noun-verb
with three reconcile verbs, Terraform-shaped, and all three sit at the top level
and again under each resource, so narrowing to one part of the machine is the
same sentence with a noun in it.

## Why there is a CLI at all

A standalone `dotfiles` CLI was considered in July 2026 and deliberately not
built, on the grounds that it would "only re-wrap existing scripts for a cosmetic
rename — maintenance cost with no capability gain." That reasoning was reversed,
because two capabilities turned out to be missing rather than merely renamed.

**`task` cannot run from outside the repository.** Task discovers `Taskfile.yml`
by walking up from the working directory, so every management action was gated
behind a `cd`. That is structural rather than cosmetic, and no amount of Taskfile
work fixes it.

**`update.sh` had no argument surface at all.** Its final line was a bare `main`.
Nothing could skip the sudo-gated system phase or refresh only personal tools.
Selective update did not exist anywhere in the repository.

The constraint that kept the tool in bash is real and unchanged: a
separately-distributed binary could never work on its own, because the CLI's job
is invoking things that exist only inside the cloned repo.
`uv tool install --editable` satisfies that constraint. The installed tool *is*
the checkout, so there is no distribution channel to buy and nothing to keep in
sync.

## `check` answers a different question from `plan`

A package a version behind is drift: expected, benign, and exactly what `apply`
is for. A machine-local value nobody set, a file only safekeep can restore, a
declaration that will not validate, a checker that crashed — those need a person.

One verb answering both meant one exit code carrying both, and the scheduled unit
sat permanently `failed` on a machine whose only fault was being a version
behind. The distinction was already in the data: `Repair` says who can fix a
change, so `plan` keeps what `apply` can fix and `check` keeps what it cannot.
`ExitCode` in `src/dotfiles/vocabulary.py` says why three is separate from one.
The periodic timer runs `check`, and the shell nudge fires on issues alone.

The split does not reach the network, though. All three verbs measure: they ask
GitHub what each declared release is at, the package managers what they are
holding back, and every plugin clone whether its remote has moved. Being invoked
is the reason to give a current answer. `--cached` declines the lot, and
`commands.MEASURES_UPSTREAM` argues why that is the flag rather than the default.

The resource doors say the same thing. `dotfiles system plan` and `dotfiles
plugins plan` take the flag and default to measuring exactly as the composite
verbs do, because a narrower door answering from a cache while the wide one
measures is two front doors disagreeing about one dataset.

How a run renders on screen is `src/dotfiles/output.py`, which argues its own
choices. None of that reaches `--json`, which a caller parses instead of the
screen; [Observability](observability.md) has its shape.

## The bootstrap prints two commands and runs neither

`./install.sh --machine NAME` gets a bare machine as far as this CLI, and then
prints the `plan` and `apply` that converge it. It validates the manifest name
itself — the only check in the system that does — because the CLI that would
answer the question does not exist yet.

Printing rather than running is deliberate. Ending in `exec dotfiles apply` meant
a bare `./install.sh` on a WSL box whose `~/.env` already named it went straight
into a half-hour networked run nobody had asked to start, and stalled on a
blocked cargo download behind the work firewall. Getting the CLI onto a machine
answers "can this box run any of this at all". Converging it answers "what should
this box become". One question is cheap and always right; the other is long and
worth planning first. Fusing them means the cheap one cannot be asked alone, and
the expensive one cannot be declined. `--offline` stays on the bootstrap, because
it decides where uv and the wheels come from, and that is settled before any CLI
exists to be told.

## `dotfiles update` updates this installation

`update` means here what it means for every other tool in the fleet: update this
tool. It pulls `--ff-only` and repairs the two things a pull can invalidate, and
`src/dotfiles/commands/manage.py` holds that sequence. An editable install goes
stale only on a changed `pyproject.toml` or `uv.lock`, because uv points at the
working tree, so code changes *are* the new code and never need a rebuild.

**`pyselfupdate` is deliberately not used, and its refusal is correct rather than
a gap.** It declines to reinstall over a `directory`/`path`/`editable`
requirement, which is the right answer. This repo publishes no releases, its
source of truth is the working tree, and installing a release over it would
destroy the thing being updated. File nothing to add releases here on the
strength of it.

For the same reason there is no update *notice*: there is no published version to
compare against. Both read-only verbs end with the honest equivalent — where the
checkout sits against the last-fetched `origin/main`, and how long ago that fetch
was. `src/dotfiles/checkout.py` reads `.git` and never the network, so the answer
is free at a prompt and correct offline, which is why it dates itself.

## The machine environment (`~/.env`)

`~/.env` is the first thing `.zshrc` sources, and where every command not given
`--machine` learns which machine it is on. It answers which machine this is
(`MACHINE`) and which features it wants running (the flags from
`install/flags.yml`), and it carries secrets that must never be checked in.
`dotfiles env` maintains it at the first stage of every apply, and
`src/dotfiles/envfile.py` holds the OVERRIDES split that makes regenerating a
file full of API tokens safe.

`MACHINE` names a manifest and the resolver derives everything else from it. No
coordinate reaches this file, for the reasons [the architecture
overview](index.md) gives.

Placing this file by hand is therefore the whole of the pre-install bootstrap.
`session.resolve_machine` reads the file when `$MACHINE` is unset, so a rebuild
that restores `~/.env` first never needs `--machine` on anything. Reading the file
rather than only the environment is what makes that work outside a login shell: a
scheduled `check` inherits no `~/.env` at all.

That bootstrap is genuinely circular, since the manifest `~/.env` names is what
generates `~/.env`. A bare machine therefore has one line to type by hand, and
only `MACHINE=`; the first `dotfiles apply --machine NAME` fills in the rest.
Hand-authoring the whole file is what left `NVIM_AI_ENABLED` set on every machine
and read by nothing, with no way to say which had drifted.

### Which gates are flags

A flag is for behavior that is present and cheap, where the only question is
whether this machine wants it running. Payload that is expensive to install stays
a manifest tool list. Config a program discovers by path and cannot branch on
(hyprland, waybar, ghostty) stays a coordinate variant under `configs/`. A
`command -v fzf` guard is not a flag and should not become one, because fzf has
no reason to be installed and unwanted. A gate earns a flag only when *installed
but off* is a state worth having.

The shell plugins qualify, because they carry both a preference and a real
startup cost. Turning the four off measures at roughly 130ms saved. The manifests
use that: the work box sets `SHELL_NUDGE: false` because the review register is
personal, and `linux-lxc-server` turns off the whole interactive plugin set. The
plugins are still *installed* there, so turning one back on mid-debugging is a
`~/.env` edit rather than a reinstall.

A plugin must be sourced at top level, never from inside a helper function. A
function scope changes what a plugin's own `typeset` calls do, so the loads stay
inline and slightly repetitive rather than factored into a `load_plugin` helper.
The other ordering hazard is `zsh-vi-mode` overwriting the whole keymap, and
`.zshrc` explains beside `apply_shell_keybindings` why that binding lives in a
named function with two callers.

### Beyond the shell

Neovim reads none of this vocabulary, and the gate it had is the argument for
keeping the rest small. `core/profiles.lua` derived a `minimal` plugin set from
`DOTFILES_CAPACITY == 'server'`, with `NVIM_PROFILE` as the override. Before the
axes split it read `PLATFORM == 'linux'`, which was the right answer for the
wrong reason — `linux` happened to be the one headless platform, so a graphical
Ubuntu desktop would have got the lean set.

Following the coordinate was the correct fix and the profile still did not earn
its keep. Exactly one machine ever reached it, the LXC, and the price was a
hand-kept allowlist of editing essentials maintained forever for one box nobody
sits at. Deleting it leaves one question — whether Neovim is embedded in VSCode —
which no coordinate answers, because it is a fact about the process rather than
about the machine.

`plugins/typos.lua` is the counter-example, and worth keeping in mind before
reaching for this vocabulary at all. It was `PLATFORM ~= 'wsl'`, then
`MACHINE_ROLE ~= 'work'`, then a test for `~/notes` — each one a label standing
in for a condition that turned out not to need expressing. It is an unconditional
remote spec: capture is scoped to `notes_root`, so a machine without one writes
nothing, and `setup()` creates no directories. The gate existed only because a
`dir =` local checkout errors on every startup when the directory is absent,
which is a fact about local specs rather than about machines.

`core/options.lua` keeps its check and spells it `WSL_DISTRO_NAME`, which WSL
sets itself. It read `DOTFILES_HOST == 'wsl'` first, on the reasoning that
win32yank genuinely is a fact about the host rather than a stand-in for one —
true, and still the wrong source, because a declared coordinate is a second
description of something the runtime already states, and `tmux.conf` was solving
the identical problem the direct way three files over. The test survives the
correction and gains a clause. If the condition can be stated as something the
code needs, state that. If the machine already announces it, read the
announcement. Reach for a coordinate only when the difference really is which
kind of machine this is, and no process on it says so.

tmux gets nothing. Every conditional in `tmux.conf` is real runtime detection —
is this pane running vim, is `$WSL_DISTRO_NAME` set, does the theme file exist,
is tpm cloned — and none of them is a preference in disguise. A flag with no
consumer is how `NVIM_AI_ENABLED` happened, so the mechanism waits until
something needs it.

## Selective installs and updates

There is no phase registry. `dotfiles apply` measures the whole plan once and
acts on it in `Stage` order. Keeping a hand-written order beside that is what let
`system/manager`, the OS package upgrade, sit at a stage no phase named and never
run at all.

A selector is a resource, or one provider inside one, and `dotfiles apply --help`
lists what each flag takes. Four hand-maintained groups (`system`, `languages`,
`tools`, `plugins`) were the rejected alternative, because their membership was a
fifth list to keep in step. A resource and a provider are what the provider
registry already knows, so there is nothing to maintain. The one group worth its
own name is `system`, because it needs sudo and dominates the runtime, and
`--skip system` is that group derived rather than declared.

**Every selector reads as well as it writes.** `plan` answers "what would `apply`
change", so a scope the write accepts and the read cannot express is not a
narrower preview but no preview at all. For a while `apply` could be narrowed to
one section with no way to rehearse it, which is the case a preview is worth most
in. What stays write-only describes *how* to write rather than what to cover:
installing from a staged bundle, or forcing an entry past what measuring
concluded. `tests/cli/test_conformance.py` asserts the split across the whole
tree, because nothing else notices a selector added to one verb and forgotten on
its sibling.

Narrowing belongs to the resolver rather than to each installer. A hand-rolled
filter block per installer is how `--mine` came to run cargo, uv and npm in full
while claiming to filter, because only the Go one honoured the owner. The rules
that fall out of doing it once are `Selection` in `src/dotfiles/engine.py`: why a
misspelt address is a usage error, why the narrowing is per resource, and why a
section brings the runtime it declared it needs.

Ownership is derived from whichever field carries it — `repo`, `github_repo`, or
a Go import path in `package` — never from a `personal` tag, because a tag has to
be remembered on every new tool and silently excludes whatever it misses.
`--owner` matters most in practice, because a newly released personal tool has to
be installed before any self-updater can maintain it, and those tools span four
sections at once.

**Scope and force are different flags.** `--package` narrows and `--reinstall`
overrules what measuring concluded. One flag carrying both — `--reinstall
lazygit` — puts a scope somewhere no other resource can see, so none of them can
honour the force. Bare, `--reinstall` covers the whole run, which is expensive
and not dangerous, and is the case `cli-design.md` § "Scope is structural: the
argument's presence selects it, never a flag" sanctions a set-wide act for.

### Install and update are one act

There is no update verb for the machine. `apply` installs what is missing and
reinstalls what differs from the newest release, and which of those a given row
needs is the verdict's answer rather than the caller's. *Differs*, not *is
behind* — `src/dotfiles/resources/packages.py` holds why a version above the
newest release is drift too, and what a downward re-version stranded.

Whether an update installs a newly declared tool must not depend on which section
of `packages.yml` it was added to. `go install @latest`, `cargo binstall` and the
release installers all create as a side effect of upgrading, while
`uv tool upgrade` and `<tool> update` cannot. A `MISSING` row and a `STALE` row
are different verdicts with different repairs, and both are reported before
either is acted on.

`dotfiles packages check` answers that on demand, and is deliberately separate
from `dotfiles machines check`, which runs on every commit: that one compares
`packages.yml` against the manifests and what can install them, and a machine
part-way through a rollout is not a repo defect that should fail a commit.

### What a provider is allowed to claim

A per-tool line must be derived from observed state: a version or ref that
changed, or a non-zero exit. It may never be derived from "the command returned",
because `uv tool upgrade`, `cargo binstall`, `npm update -g` and
`git pull --quiet` all exit 0 whether or not anything changed. The `Change`
supplies that, and its `Outcome` names what was repaired. The one place a
before-and-after snapshot survives is `clone.pull`, which reports the commit
either side, because `git pull --quiet` on a current clone prints nothing at all.

Where a tool already reports its own outcome accurately,
`src/dotfiles/providers/custom.py` delegates rather than re-deriving one: `theme`
and `font` run their own `update` and propagate the exit code. Matching a
sentinel string against that output is the trap. It always missed, printing
`theme updated` on every run, over an unconditional `exit 0` that kept a genuine
failure out of the report.

## Logins are checked and never repaired

A converged machine is not necessarily a working one. Every binary can be
installed, every symlink deployed and every flag set while the CLIs that do the
work sit logged out. That was the Arch box on 2026-08-12, with `learning`,
`meso`, `nomad` and `atuin` all unauthenticated and `dotfiles check` reporting a
screen of converged rows. `src/dotfiles/resources/auth.py` closes that gap, and
its module docstring carries the decisions inside it: why the manifest names
which tools while the module says how each is asked, why every probe is local and
which measurement picked it, and why a finding is `Repair.BY_HAND` that `apply`
can never reach.

**A machine that will never hold an atuin account does not declare one.** `auth:`
is the roster of logins a machine has to be able to make, so a permanent no
belongs there rather than in a row explaining itself on every run. The work box
is that machine: its copy of the config is the `trust/nonfleet` one, sync is off
because a git-only node behind a corporate firewall is the wrong place to send
shell history from, and `scheduler.yml` leaves atuin out for the same reason in
its own words.

## What lives in `apps/` and what leaves it

The `apps/` scripts (`notes`, `packup`, …) are **independent user tools** with
their own identity and `doit find` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.

An app leaves this directory when its data outgrows a file. `patterns` captured
timestamped fragments into a per-machine JSONL that reached no other desk, and a
tool for finding patterns over time needs every entry rather than one box's — so
it became `icb patterns` against the ichrisbirch API. The test is the store, not
the script: a file-backed app whose file has to roam is already an API client
that has not been written yet.

Everything else is answered from the source: `dotfiles --help` names the
resources, and each module under `src/dotfiles/resources/` says how its resource
is measured.
