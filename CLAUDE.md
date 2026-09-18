# Claude Code - Dotfiles Development Context

Only what is specific to this repo. Universal conduct is `~/.claude/CLAUDE.md`; how the fleet builds
things is `fleet standards search`.

## The checked-out branch is deployed machine state

`configs/`, `shell/` and `apps/` are symlinked live into `$HOME`, and the `dotfiles` CLI is installed
**editable** against `src/`. Switching branches changes both the config this machine runs and the
tool that deploys it, and nothing announces it.

- **Every change starts in a worktree, without checking for peers first.** `worktree new <slug>` is
  the first tool call. The usual size rule does not decide it here, because being on the wrong branch
  costs a machine running that branch rather than a lost commit. `worktree land` catches the primary
  checkout up afterwards, which here is a redeploy.
- **`~/dotfiles` itself stays on `main`.**
- **`EnterWorktree(path=…)` refuses when the session's directory is outside this repo.** From `~/dev`,
  drive the worktree by absolute path instead.
- **One worktree per stack, at its top.** `rebase.updateRefs` silently skips a stacked branch checked
  out in a second worktree, leaving that ref on pre-rebase commits.
- **Run `dotfiles` from `~/dotfiles`, never from inside a worktree** — `cd ~/dotfiles &&` is the
  prefix. A shell without the exported `DOTFILES_DIR` resolves the repo root by walking up from the
  CWD and deploys the worktree's config over the machine's.
- **To run the branch's logic against the real machine**: `DOTFILES_DIR=/home/chris/dotfiles uv run
  --quiet dotfiles <cmd>` from inside the worktree.
- **A `uv run` in a worktree leaves a `.venv` there**, which the packages resource reports as
  undeclared binaries. That is the harness, not a finding.
- `dotfiles check` and both apply paths warn when the checkout is off `main` (`checkout.stray_branch`).
  A warning, not a refusal: being on a branch here is legitimate, and the failure guarded against is
  not knowing.

What to run to verify a change is `tests/README.md`; the roster is `task --list-all | rg test:`.

## dotfiles configures machines, never fleet data

A registry of repos, a roster of machines, a body of standards — these are the fleet's own data, and
dotfiles never owns, clones, installs, locates or checks them. A nonfleet box runs this same engine
with none of it, so an apply or a check that reaches for that data breaks there.

- **Permitted**: a fleet-scoped config file under `configs/trust/fleet/` naming a path.
  `configs/trust/nonfleet/` carries the other machine's answer.
- **Forbidden**: a fleet path hardcoded in `configs/common/`, `apps/common/` or `shell/common/`; a
  manifest declaring a fleet data clone; an engine resource that clones, pulls or reports on fleet data.
- **When common code needs the location**, it reads an environment variable declared in
  `install/flags.yml` below the OVERRIDES marker, the same way as `WINDOWS_USER`. No fallback default:
  a default is the hardcoding one indirection later, and it produces a wrong answer instead of a
  missing-value error.

## Where things go

**Four install patterns**, chosen by what a thing is, never by how large it grew:

| Pattern | Declared in | Installer |
| --- | --- | --- |
| Go app | `packages.yml` `go_tools` | `providers/gotool.py` → `~/go/bin/` |
| Script app | `apps/common/` or `apps/<axis>/<value>/` | symlinked flat to `~/.local/bin/` by `TREES` in `resources/symlinks.py` |
| Personal CLI (theme, font) | a function in `providers/custom.py` | clone to `~/.local/share/<tool>/`, symlink the bin |
| Python tool from git | `packages.yml` `git_uv_tools` **and** each machine's manifest | `providers/uvtool.py` |

An app that is part of the CLI's own surface becomes a module in `src/dotfiles/` with a
`[project.scripts]` entry; a standalone tool stays in `apps/`. `prs` cannot move at all:
`declared_closure()` in `create_bundle.py` keeps only `==` requirements, so its git-sourced
`pytermstyle` would be dropped silently and the offline bundle would ship missing a dependency.
`docs/learnings/app-installation-patterns.md` has the detail.

**Choosing an install method.** `install/packages.yml` is the source of truth, and its header maps
each section to a method. OS utilities, GUI apps and compiled libraries go to `system_packages`. Rust
CLIs go to `cargo_packages` via `cargo binstall`, falling back to the system manager only where
upstream ships no release binary. Tools needing the latest upstream go to `github_releases`. Language
runtimes go through `providers/toolchain.py` — uv, rustup, the go.dev tarball, and fnm for Node —
never a system language package; none is subscribed to, so a machine gets Go because it declared
`go_tools`. Language-scoped tools use their own manager.

**Node is fnm, and repos pin different majors.** fnm's default version is linked by
`toolchain.py`; `.zshenv` puts that alias on PATH so non-interactive shells get it, and `.zshrc` adds
`--use-on-cd` so a repo's `.nvmrc` wins interactively. The brew or pacman node package is only the
bootstrap npm. *Rejected:* nvm, whose shell-function design is invisible to non-interactive shells —
a binary does not share that fault.

**`install/system.yml` holds what a machine *is* once the packages are on it** — group memberships,
unit enablement, files under `/etc`, the login shell. `packages.yml` deliberately holds none of that.
Scripts whose subject is the repo rather than a machine go in `install/ops/`.

**A new GitHub release tool is one function in `providers/releases.py` plus its `packages.yml`
entry.** `providers/ghrelease.py` is the engine. Verification is required by default; an entry that
cannot satisfy it declares `checksum: unpublished` or `checksum: unlisted`, and `go_tools`,
`cargo_packages` and `winget_packages` use the same field (`catalog.CHECKSUM_STATES`).
`docs/architecture/github-releases.md` and `offline-bundles.md` are the account.

**Shell libraries** live in `~/.local/shell/` — `flags.sh` for whether a feature is wanted here,
`logging.sh` for logged scripts, `formatting.sh` for interactive output, `error-handling.sh` for
strict mode and cleanup. `docs/architecture/shell-libraries.md`. A standalone script in `apps/` runs
in its own process, so it sources `logging.sh` itself.

**Resolve the repo root as `DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"`.** The
CLI runs from any directory, so a bare `git rev-parse` resolves whatever repo the user is standing
in. Never navigate with `$(cd "$(dirname ...)/../.." && pwd)`.

## The coordinate model

**`MACHINE` is the one hand-chosen value.** It selects a manifest, and the manifest places the machine
on the six axes in `src/dotfiles/coordinates.py`. Nothing is detected, because a guess cannot tell a
fleet network from a nonfleet one, or a workstation from a server. Never enumerate the coordinate
directories in prose — `eza -1 -D configs apps shell` lists the ones that exist. A manifest names a
`platform:` bundle or declares `coordinates:` directly, never both. Why the fused `PLATFORM` string
was split, and why a `MACHINE_ROLE` axis was tried and removed: `docs/architecture/index.md`.

`shell/` is the one tree that keeps `<axis>/<value>/` in its deployed path under `~/.local/shell/`,
so a sourced file says which coordinate asked for it. `configs/` and `apps/` deploy flat.

**A deployed path lives in exactly one directory.** `declared()` in `resources/symlinks.py` appends
without deduplicating, so the same relative path in `common/` and a coordinate directory is a
collision, never an override. `shell/` holds **layers**, and every one a machine selects is sourced.
`configs/` and `apps/` hold **variants**, and exactly one file arrives — so a config differing on one
machine moves out of `common/` whole rather than being patched.

**Machine-local shell code goes in `~/.local/shell/local.sh`**, sourced last by `.zshrc` and never in
this repo, because it holds internal hostnames. safekeep restores it, so it is legitimately absent
between an apply and the restore step. A generic mechanism belongs in its coordinate layer; the values
naming one organization's hosts, and any workaround only that network forces, go in the local file.

**A feature flag** in `install/flags.yml` is for code that is present and cheap, where the only
question is whether this machine wants it. Expensive payload stays a manifest tool list. Config a
program finds by path and cannot branch on (hyprland, waybar, ghostty) stays a coordinate variant.

**This repo does not use `stow`.** After adding, removing or renaming anything under `configs/`,
`apps/` or `shell/`, run `dotfiles symlinks apply` — idempotent, one verb for the whole declaration.
It decides per link and never unlinks everything first: a remove-everything pass gave Hyprland a
window to find its config gone and write itself a default. `test_a_deployed_config_is_never_touched_by_a_later_run`
pins it. Stale symlinks show as Neovim "module not found" or a config not being picked up.

**Theme configs name `current`, never a theme.** `theme` installs each app config under the theme's id
and points a stable `current` symlink at it. `rg -l --hidden '/current\b' configs/` finds the pointers;
`--hidden` is load-bearing, since every one is under a `.config` directory.

## Things that bite

**Generated config is never hand-edited.** `.pre-commit-config.yaml`, `.github/workflows/validate.yml`,
`.editorconfig`, `.shellcheckrc` and `.markdownlint.yaml` come from forge (`forge repos apply precommit`,
`forge repos apply ci`); anything outside a `# > custom:` marker is overwritten. Two things specific
here: a repo CI step uses `# > custom:after:all` as a whole job, because an `after:<block>` section
absorbs the following jobs and then duplicates them. And shell style lives in `.editorconfig`, which
shfmt reads — a printer or parser flag on the shfmt hook replaces that file wholesale. The dies are
fleet-wide by default; `--filter dotfiles` narrows one to this repo.

**Zsh is XDG and correct as it is.** `ZDOTDIR` is set system-wide to `~/.config/zsh`, from
`/etc/zshenv` or `/etc/zsh/zshenv` depending on distribution — `install/system.yml` declares both
through `path` and `alternate_path`. There is no `.zprofile` or `.zshenv` in `$HOME`, and there
should not be.

**Never run `./install.sh` or `dotfiles apply` in a Claude Code session.** The apply needs
interactive sudo. Test a provider directly, or in a Docker container with passwordless sudo.

**Homebrew builds no new Intel bottles, and the macOS machines here are Intel.** Intel drops to Tier 3
in September 2026 and is unsupported from September 2027. This is settled; the errors are the expected
consequence, not a defect to chase. `brew upgrade` fails and the run is unconverged, because
`UPGRADE` in `providers/syspkg.py` is whole-manager — while `dotfiles packages check` stays green,
because it measures presence and a broken binary is present. A half-done upgrade breaks a linked
binary with `Library not loaded`, because brew builds a formula from source as a *dependency* but
refuses as the *dependent*. The repair is `brew install --build-from-source <name>`, confirmed with
`otool -L` rather than the exit code. The `Tier 3 configuration` line in a no-bottle error is
boilerplate about source builds, not the machine's tier. Before assuming a source build, check the
formula still has an Intel bottle — the bare macOS keys are Intel:

```bash
curl -sf https://formulae.brew.sh/api/formula/<name>.json | jq -r '.bottle.stable.files | keys | join(" ")'
```

**macOS**: GNU coreutils are prepended to PATH unprefixed, for scripts as well as shells. Development
uses uv-managed Python; Homebrew Python stays only where `brew uses --installed python@X.XX` needs it.

## Documentation

Docs here are a reference for a reader six months later. Write in the imperative ("Copy the config
file", never "You should"), in paragraphs that keep the reasoning, factual rather than promotional.
Add every new doc to `mkdocs.yml` navigation. Notes naming nothing in this repo belong on the hub
(`~/docs`).

**A doc earns its lines by explaining what the code cannot state** — a decision, a rejected
alternative, a non-obvious constraint, a measured tradeoff. Never write a list a command produces:
`task --list-all`, `packages list --section=<x>`, `eza -1 install/manifests/`, `<tool> --help`. If
`--help` would regenerate a section correctly, delete it. `docker.md`, `tmux-sessions.md` and
`custom-installers.md` are the models; nothing in them changes when code changes.
`docs/development/docs-audit.md` is the dated baseline — add to it, never edit it.

**A page never explains a mechanism its module docstring explains.** Two sources for one subject
diverge. `task docs:duplication` ranks pages by six-word runs shared with docstrings under
`src/dotfiles/`.

**Search `docs/learnings/` by symptom before diagnosing anything** — `rg -i "no route to host"
docs/learnings/`. Nothing surfaces the directory at the moment something breaks, so it is only
consulted when searching it is a deliberate first step. A learning quotes its error verbatim, because
the literal string is what gets searched. Keep one to 30–50 lines: Problem, Solution, Key Learnings.

`todo.md` is for creating future work items. Never use it for planning, move it to `.planning`, or
change it otherwise.

The `dotfiles` CLI's three reconcile verbs are `plan`, `apply` and `check` — `check` reports what is
*wrong*, which a machine merely behind on versions is not. `dotfiles --help` and
`docs/architecture/management-interface.md` cover the rest.
