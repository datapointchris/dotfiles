# Management Interface

How you drive this repository: a `dotfiles` CLI that works from anywhere, a `task`
front door for work inside the repo, and one shared implementation underneath both.

## Layering

Two front doors sit over the same implementation, so neither can drift from the other:

```text
dotfiles <noun> <verb>       task <verb>
             \                  /
              src/dotfiles/            the package: phase walk, symlinks, catalog
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

Bootstrapping a bare machine is `./install.sh --machine NAME`, and its whole job is
getting to this CLI: check `git` and `tar`, stage an offline bundle if one is present,
install uv, `uv tool install --editable`, then `exec dotfiles apply`. It validates the
manifest name itself — the only check in the system that does — because the CLI that
would answer the question does not exist yet.

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

`~/.env` is the first thing `.zshrc` sources and the first thing `install.sh` reads. It
answers three questions — which machine this is (`MACHINE`), where it sits on each of
the six coordinate axes (the `DOTFILES_*` block, plus `PLATFORM` where the tuple has a
bundle name), and which features it wants running (the flags from `install/flags.yml`) —
and it also carries secrets and machine-local values that must never be checked in.

`MACHINE` is the only one of the three that is chosen: it names a manifest, and
everything else is derived from that manifest by the resolver. The coordinates are what
select the overlay directories under `configs/`, `shell/` and `apps/`, so a shell reads
them directly — `.zshrc` builds its source list from exactly those six variables. Placing this file by
hand is therefore the whole of the pre-install bootstrap — `install.sh` sources it with
`set -a` before any phase, so a rebuild that copies `~/.env` into place first never needs
`--machine`.

It used to be hand-authored, which made it the one piece of setup with no source of
truth: a flag added to the repo reached no existing machine, and nothing could say which
machines had drifted. `NVIM_AI_ENABLED` survived that way for a long time — set
everywhere, read by nothing.

Now `install.sh` generates it and `dotfiles env` maintains it.

Everything above the `# OVERRIDES` marker comes from the manifest and `flags.yml` and is
rewritten on every apply. Everything below it is preserved verbatim, which is what makes
the file safe to regenerate while it holds API tokens. A file with no marker predates
generation, so all of it is treated as hand-written and moved below — lossless by
construction. Syncing also takes a `.bak` and writes through a temp file and a rename,
because a half-written `~/.env` would take a machine's secrets with it.

The bootstrap is genuinely circular — `~/.env` names the manifest, and the manifest
generates `~/.env` — so a bare machine still has one line to type by hand. Only
`MACHINE=` though; `install.sh --machine NAME` fills in the rest on first run.

Every generated line is written as `export NAME="${NAME:-value}"`, so the ambient
environment still wins for a single shell — `ZSHRC_DEBUG=1 zsh` and
`PLATFORM=wsl ./install.sh` both keep working without editing the file.

Flags are for behavior that is present and cheap, where the only question is whether this
machine wants it. Payload that is expensive to install stays a manifest tool list, and
config a program discovers by path and cannot branch on (hyprland, waybar, ghostty) stays
a coordinate overlay under `configs/`.

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

Neovim reads the same vocabulary. `core/profiles.lua` derives its plugin profile from
`DOTFILES_CAPACITY` — a machine declaring itself a server has already said everything
needed to pick the minimal set — with `NVIM_PROFILE` kept as the override for anything
that does not follow. That removed a second variable which had to be set by hand on
every server. It read `PLATFORM == 'linux'` until the axes split, which was the right
answer for the wrong reason: `linux` happened to be the one headless platform, so a
graphical Ubuntu desktop would have got the lean set.

`plugins/typos.lua` is the counter-example, and worth keeping in mind before reaching for
this vocabulary at all. It was `PLATFORM ~= 'wsl'`, then `MACHINE_ROLE ~= 'work'`, then a
test for `~/notes` — each one a label standing in for a condition that turned out not to
need expressing. It is now an unconditional remote spec: capture is scoped to `notes_root`,
so a machine without one writes nothing, and `setup()` creates no directories. The gate
existed only because a `dir =` local checkout errors on every startup when the directory is
absent, which is a fact about local specs rather than about machines.

`core/options.lua` keeps its check and now spells it `DOTFILES_HOST == 'wsl'`, because
win32yank genuinely is a fact about the host rather than a stand-in for one. The test: if
the condition can be stated as something the code needs, state that; reach for a
coordinate only when the difference really is which kind of machine this is — and then
reach for the *one* axis that decides it, not the whole point.

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
dotfiles apply --skip system          # skip the sudo-gated, slowest part
dotfiles apply --skip plugins/tpm     # one provider, not all of plugins
dotfiles packages apply --source cargo_packages   # one section
dotfiles apply --owner datapointchris # only tools traceable to that owner
dotfiles apply --skip system          # a whole resource
dotfiles apply --skip plugins/tpm     # one provider inside one, leaving its neighbours
```

Owner narrowing takes only the phases whose contents can be traced to a GitHub owner,
and skips the rest rather than silently running them in full. Ownership is derived from
whichever field carries it — `repo`, `github_repo`, or a Go import path in `package` —
not from a `personal` tag, because a tag has to be remembered on every new tool and
silently excludes whatever it misses.

`dotfiles apply --owner` is the command that matters most in practice: a newly released
personal tool has to be installed before any self-updater can maintain it, and those
tools span four sections (`go_tools`, `github_releases`, `custom_installers`,
`git_uv_tools`), so owner is the only selector that reaches all of them at once.

An address is `resource` or `resource/provider`, and one naming neither is a usage error
rather than an empty selection. A run that accepted a misspelt `--skip` would install the
sudo-gated phase the caller was avoiding and report success — which is also why a trailing
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
entries, and `Plan.providers` says which phases have anything left to do. It was a
hand-rolled filter block per installer script before that, and only the Go one honoured
the owner — so `--mine` ran cargo, uv and npm in full while claiming to filter.

### Install and update are one act

There is no update verb. `apply` installs what is missing and upgrades what is behind,
and which of those a given row needs is the verdict's answer rather than the caller's.

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

### What a phase is allowed to claim

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
| Package queries | `src/dotfiles/parse_packages.py` — types, manifests, owners |
| Declaration drift | `dotfiles machines check` — packages.yml vs manifests vs installers |
| Machine drift | `dotfiles plan` — this machine vs what its manifest declares |
| Tool discovery | `toolbox` (across all installed tools) |
| Cross-repo operations | `forge` |

The `apps/` scripts (`notes`, `packup`, `patterns`, …) remain **independent
user tools** with their own identity and `toolbox` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.
