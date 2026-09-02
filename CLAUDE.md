# Claude Code - Dotfiles Development Context

General conventions this repo follows are maintained outside it, and none of them is
restated here.

**This file contains ONLY dotfiles-specific rules and patterns.**

**dotfiles does not manage fleet data** (⚠️ MANDATORY): dotfiles configures *machines*. A registry
of repos, a roster of machines, a body of standards — these are the fleet's own data, and dotfiles
never owns, clones, installs, locates or checks them. "It would be convenient for `dotfiles check`
to verify it" is exactly the reasoning this forbids: the moment an apply or a check reaches for
that data, a machine outside the fleet is running an engine that expects something it will never
have, and the tool that legitimately owns the data has been bypassed.

- **Permitted**: a *fleet-scoped config file* under `configs/trust/fleet/` naming a path. It is
  deployed configuration for a tool, it never lands off the fleet, and `configs/trust/nonfleet/`
  carries the other machine's answer. This is the trust axis doing its job.
- **Forbidden**: anything in `configs/common/`, `apps/common/` or `shell/common/` hardcoding a
  fleet path; a manifest declaring a fleet data clone; a resource in the engine that clones,
  pulls, or reports on fleet data.
- **When common code genuinely needs the location**, it reads an environment variable declared in
  `install/flags.yml` below the OVERRIDES marker — the same mechanism as `WINDOWS_USER`. The repo
  declares that a machine *needs* a value and never learns what it is, and `dotfiles check` fails
  while it is unset. No fallback to a default path: a default is the hardcoding, one indirection
  later, and it silently produces a wrong answer instead of a missing-value error.

This is the counterpart to `~/.claude/CLAUDE.md` § "Nothing calls `fleet` except what the fleet is
for". That rule stops a tool from *executing* fleet; this one stops dotfiles from *adopting* the
fleet's data as its own responsibility. Both exist because the work box runs this same engine with
none of it.

**File Naming and Organization**:

- Markdown filenames are lowercase with hyphens
- ALWAYS add new documentation to `mkdocs.yml` navigation

**Shell Script Patterns**:

- ALWAYS use `DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"` to get repo root. The exported value must win: `install.sh` exports it, and the `dotfiles` CLI runs from any directory, so a bare `git rev-parse` resolves to whatever repo the user happens to be standing in — or aborts outright outside one.
- NEVER use relative path navigation like `$(cd "$(dirname ...)/../.." && pwd)`

**App Installation Patterns** (⚠️ CRITICAL - Four distinct patterns):

1. **Go Apps** (sesh, task): Installed via `go install` from packages.yml
   - Defined in `packages.yml` under `go_tools` with `package` field (go install path)
   - Installer: `src/dotfiles/providers/gotool.py`, through `dotfiles packages apply`
   - Development in `~/tools/{app}/`, push to GitHub, `go install` gets latest
   - Binary location: `~/go/bin/`

2. **Symlinked Script Apps** (notes): Symlinked from repo
   - Located in `apps/common/` or an `apps/<axis>/<value>/` variant as executable files (bash, or Python via a `uv run --script` / `python3` shebang)
   - **Coupling is what moves an app out of here, never size.** An app that is part of the CLI's
     own surface becomes a module in `src/dotfiles/` with a `[project.scripts]` entry. A standalone
     tool stays here however large it grows, because the move buys the package's dependency
     closure, install lifecycle and release, and a standalone tool pays all three for nothing.
     `prs` cannot make the move at all: its git-sourced `pytermstyle` would have to enter
     `[project.dependencies]`, and `declared_closure()` in `create_bundle.py` keeps only
     requirements containing `==`, so a git URL is dropped with no error and the offline bootstrap
     builds a bundle missing a dependency
   - Symlinked to `~/.local/bin/`, flattened — the axis path is dropped at the destination
   - Deployed by `TREES` in `src/dotfiles/resources/symlinks.py`, which names that destination

3. **Personal CLI Tools** (theme, font): Git clone + symlink
   - Installed by a function in `src/dotfiles/providers/custom.py`
   - Clone to `~/.local/share/{tool}/`, symlink bin → `~/.local/bin/`
   - Development in `~/tools/{app}/`, push to GitHub, run `{tool} update`

4. **Python Tools from git** (safekeep, refcheck, syncer, indy, …): `uv tool install` from a git repo
   - Defined in `packages.yml` under `git_uv_tools` with `name`, `repo`, `description`
   - Installer: `src/dotfiles/providers/uvtool.py`; binary lands in `~/.local/bin/`
   - **Each machine's manifest also lists it** — unlike a symlinked app, which every machine
     with `apps/` symlinks gets automatically, a git uv tool reaches only the machines naming it
   - This is where a Python app goes once it is its own project, with a repo, a release and a
     version of its own — again what the thing is, not how large it got

See `docs/learnings/app-installation-patterns.md` for full details.

**Standards First**: Prefer the industry-standard default over a local invention, and where you deviate, write the reason down. Conventional commits are enforced at `commit-msg` rather than preferred, so that one is not a judgment call.

**Generated Config — Never Hand-Edit** (⚠️ MANDATORY):

`.pre-commit-config.yaml`, `.github/workflows/validate.yml`, `.editorconfig`, `.shellcheckrc` and
`.markdownlint.json` are generated by forge from this repo's `toolchain.components` in
`~/dev/repos.json`. Regenerate with `forge repos apply precommit` and `forge repos apply ci`;
anything edited outside a `# > custom:` marker is overwritten on the next sync. `~/tools/forge/CLAUDE.md` owns the marker semantics and the block/config split.

Two things specific to this repo:

- Repo-specific CI steps use `# > custom:after:all` and must be a whole job. An `after:<block>`
  section has nothing terminating it before the next job key, so regeneration absorbs the following
  jobs into it and then emits duplicates.
- Shell style lives in `.editorconfig`, which shfmt reads directly. Never put a printer or parser
  flag on the shfmt hook — one flag replaces the file wholesale instead of merging with it.

The dies are **fleet-wide by default**: either one rewrites every active repo in the registry, not
just this one. The working directory is not a scope. Each repo's target comes from its registry
entry, so running the command from inside this repo, or from a worktree of it, changes nothing
about where the output lands. `--filter dotfiles` is what narrows it to this repo. Run unscoped,
check `git status` across the portfolio afterwards.

**Critical Bash Gotcha - Arithmetic with set -e** (⚠️ This has caught us 4+ times):

- `((COUNTER++))` returns 0 (false) when COUNTER is 0, causing `set -e` to exit the script
- **Always use:** `COUNTER=$((COUNTER + 1))` instead of `((COUNTER++))`
- **Or use:** `((COUNTER++)) || true` to prevent exit
- This affects any arithmetic expression that evaluates to 0: `((VAR--))`, `((VAR *= 0))`, etc.

**Shell Libraries** (`~/.local/shell/`) — see `docs/architecture/shell-libraries.md`:

| Scenario | Library | Functions |
| --- | --- | --- |
| Is this feature wanted here? | flags.sh | `flag_enabled`, `flag_classify` |
| Logged/monitored scripts | logging.sh | `log_info/success/warning/error/fatal` |
| Visual/interactive scripts | formatting.sh | `print_success/error/warning/info` |
| Visual structure | formatting.sh | `print_header/section/banner/title` |
| Cleanup and strict mode | error-handling.sh | `enable_strict_mode`, `register_cleanup` |

**GitHub Release Installers** (⚠️ Python, not a script per tool):

- A new release tool is one function in `src/dotfiles/providers/releases.py` naming its
  asset, plus its `packages.yml` entry. There is no script to write, and
  `dotfiles machines check` fails an entry that has neither
- `src/dotfiles/providers/ghrelease.py` is the engine every one of them goes through
- Verification is required by default; an entry that cannot satisfy it declares
  `checksum: unpublished` or `checksum: unlisted` and is measured against the live
  release by `tests/install/test_release_urls.py --e2e`
- See `docs/architecture/github-releases.md`

**Zsh Configuration Setup** (⚠️ This is the CORRECT setup - do not second-guess it):

- `ZDOTDIR` is defined system-wide pointing to `~/.config/zsh`. Which file holds it is per-distribution — `/etc/zshenv` on some, `/etc/zsh/zshenv` on Arch and Debian. `install/system.yml` declares both through `path` and `alternate_path`; never hardcode one
- There is NO `.zprofile` or `.zshenv` in the home directory (and there should NOT be)
- `.zshrc` is located in `~/.config/zsh/.zshrc` (symlinked from dotfiles repo)
- This XDG-compliant setup is intentional and correct
- Standalone shell scripts in `apps/` must source logging.sh library if they need logging (they run in their own bash process, not in the shell environment)

**Installation Script Testing**:

- `install.sh` bootstraps the CLI and stops, printing the `dotfiles apply` that converges the machine. It is the apply that needs sudo, and Claude Code cannot provide interactive sudo
- Test individual providers directly, or use Docker containers with passwordless sudo
- Do NOT run `./install.sh` or `dotfiles apply` directly in Claude Code sessions

## Package Management Philosophy

This dotfiles setup maintains a clear separation between system package managers and language-specific version managers for cross-platform consistency. `install/packages.yml` is the single source of truth for which method installs each tool; the header comment there maps every section to its install method. To avoid drift, this file describes the *principle* for choosing a method, not per-tool lists.

**Choosing an install method** (by what a tool is, not its name):

- **OS-level utilities, infrastructure tools, GUI apps, compiled libraries** → system package manager (`system_packages`: apt/pacman/brew). This is the default for anything the OS packages well.
- **Rust CLI tools** → `cargo binstall` (`cargo_packages`), which downloads prebuilt release binaries. Falls back to `system_packages` only when upstream ships no release binary (binstall would compile from source) or a native package is required on a platform (e.g. Intel-macOS bottles).
- **Tools needing the latest upstream version, or with their own downstream manager** → prebuilt `github_releases`.
- **Language runtimes** → version managers, never system language packages: **uv** (Python), **rustup** (Rust), plus the Go tarball from go.dev. All four install through `src/dotfiles/providers/toolchain.py`, and none is subscribed to — a machine gets Go because it declared `go_tools`. **Node.js uses fnm**, whose default version that module pins and links; `.zshenv` puts that alias on PATH so non-interactive shells get it, and `.zshrc` adds `--use-on-cd` so a repo's `.nvmrc` wins interactively. The brew/pacman node package remains only as the bootstrap npm. Per-project switching is used — repos pin 24 and 26 — and nvm was removed for the wrong reason: the real fault was its shell-function design being invisible to non-interactive shells, which a binary does not share.
- **Language-scoped tools** → that language's manager: `npm_globals`, `uv_tools`, `go_tools`. Language servers are usually npm.

**Platform Notes**:

- GNU coreutils on macOS are prepended to PATH (unprefixed) for universal use in both interactive shells and scripts
- Homebrew Python only kept if required by `brew uses --installed python@X.XX`
- All development uses uv-managed Python, not system Python

**Homebrew builds no new Intel macOS bottles, and both Macs are Intel**: a formula keeps whatever
Intel bottle it last published and has none once it is rebuilt, so the set with no bottle only
grows. Intel drops to Tier 3 in September 2026 and is unsupported from September 2027. Do not
re-derive this — it is settled, and the errors below are the expected consequence rather than a
defect to chase.

- **`brew upgrade` fails and the run is unconverged.** `dotfiles apply` reports
  `system/manager/brew: brew upgrade exited 1`, because `UPGRADE` in `providers/syspkg.py` is
  whole-manager and brew refuses a formula with no bottle. `dotfiles packages check` stays green
  regardless: it measures presence, and a broken binary is present.
- **A half-done upgrade breaks a linked binary**, reported as `Library not loaded` from `dlopen`.
  brew builds a formula from source without asking when it is pulled in as a *dependency*, and
  refuses when it is the *dependent* being upgraded. So a library stack moves to a new soname
  while the tool linked against it stays behind.
- **The repair is `brew install --build-from-source <name>`.** The dependencies are already
  installed by the upgrade that broke it, so only that formula compiles. Confirm with `otool -L`
  that the extension picked up the new library rather than trusting the exit code.
- **Ask whether a formula still has an Intel bottle** before assuming a source build is needed.
  The bare macOS keys are Intel; `arm64_*` is Apple Silicon:

```bash
curl -sf https://formulae.brew.sh/api/formula/<name>.json | jq -r '.bottle.stable.files | keys | join(" ")'
```

The `Tier 3 configuration` line brew prints with a no-bottle error is boilerplate on every such
message. It describes building from source, not the machine's tier.

## Project Overview

A cross-platform dotfiles repository with manifest-driven installation and shared configurations, overridden per coordinate rather than per platform. The repository emphasizes automation, documentation, and ergonomic developer workflows.

**This repo does not use `stow`** — symlinking is self-managed by the symlink manager (`dotfiles symlinks apply`). Don't reach for stow conventions or assume a stow-shaped layout.

**Directory Structure**:

- `configs/` - Configurations (what gets deployed), as `common/` plus `<axis>/<value>/` variants
- `apps/` - Personal CLI applications (bash or Python scripts), same layout, symlinked to `~/.local/bin/`
- `shell/` - Shell source files, same layout, symlinked to `~/.local/shell/` — and the only one of
  the three that keeps `<axis>/<value>/` in the deployed path, since nothing but `.zshrc` reads there
  and it makes a sourced file say which coordinate asked for it
- `src/dotfiles/` - The Python package: one importable tree, one console script per
  `[project.scripts]`. Symlink deployment is `resources/symlinks.py`; `symlinks/core.py` holds
  the helpers it walks the tree with
- `install/` - Repository management tools
  - `manifests/` - Machine manifests (YAML defining what to install per computer)
  - `offline/` - Offline installation support (connectivity testing, bundles)
  - `wsl/` - The one platform-specific install directory left (Windows font, `.wslconfig`, docker repo and images)
  - `ops/` - Scripts whose subject is the repo itself rather than a machine. `docs.sh` is run by hand; the two Python sweeps are pre-commit gates as well as Taskfile targets, so a new one belongs here whether or not a person invokes it
  - `common/` - `lib/`, the shared libraries an installer script sources
  - `packages.yml` - Package definitions
  - `system.yml` - System configuration: group memberships, unit enablement, files under `/etc`, the login shell. What a machine *is* once the packages are on it, and the half `packages.yml` deliberately does not hold (`docs/architecture/system-configuration.md`)
- `docs/` - MkDocs-based documentation site
- `.claude/` - `commands/`, the repo-scoped slash commands for Claude Code
- `.planning/` - **NOT TRACKED BY GIT** - Ephemeral planning guides and status tracking

**Key Systems**:

- **Machine Manifests** - YAML files in `install/manifests/` defining what to install per computer type. A manifest resolves its coordinates through a `platform:` bundle name or declares `coordinates:` directly — never both, because two spellings of one fact is the drift the split exists to end
- **Shell Files** - `shell/` holds `common/` plus `<axis>/<value>/` layers; symlinked to `~/.local/shell/` by `dotfiles symlinks apply`
- **Six axes, one hand-chosen value** - `MACHINE` is the only thing chosen by hand; it selects a manifest, and the manifest says where the machine sits on each of the six axes in `src/dotfiles/coordinates.py` — package manager, OS family, display stack, host, network trust, capacity. `dotfiles symlinks apply` deploys the `<axis>/<value>` directories that point selects and prunes the ones it no longer does, so `~/.local/shell/` is the resolved answer and `.zshrc` globs it. No coordinate reaches `~/.env`, which carries `MACHINE` and the feature flags alone. Nothing is detected: a guess cannot answer whether a box is on a fleet or nonfleet network, or whether it is meant to be a workstation or a server. **Never enumerate the coordinate directories in prose** — read `AXIS_DIRS` and the enums beside it, or run `eza -1 -D configs apps shell` for the ones that exist, because an axis earns a directory only where something actually differs along it. Why the fused `PLATFORM` string was split, and why a `MACHINE_ROLE` axis was tried and removed before it: `docs/architecture/index.md`
- **A deployed path lives in exactly one directory** - `declared()` in `src/dotfiles/resources/symlinks.py` walks each coordinate directory and appends without deduplicating, so the same relative path in both `common/` and a coordinate directory is a collision producing two links at one target, never an override. There is no merge step: a variant carries the whole file, which is why a config that differs on one machine moves out of `common/` rather than being patched on top of it. This is the word to get right — `shell/` holds **layers** and every one a machine selects is sourced, additively; `configs/` and `apps/` hold **variants** and exactly one file arrives
- **Machine-local shell code goes in `~/.local/shell/local.sh`** - Declared as a `required_files` entry in `install/flags.yml` and sourced last by `.zshrc`, but never present in this repo: it holds employer hostnames and the like. Restored by safekeep rather than installed, so it is legitimately absent between `dotfiles apply` and the restore step of a rebuild — which is what `dotfiles check` reports. A mechanism that is generic (mounting a Windows share) belongs in the coordinate layer that owns it; the values naming an employer go in the local file, and so does any workaround only their network forces — `update-tldr` reads as a WSL function and is really a blocked-download function, which is why it sat in the layer for months
- **Feature Flags** - `install/flags.yml` declares every on/off switch; shell code tests them with `flag_enabled` from `flags.sh`. A flag belongs there only when the code is present and cheap and the only question is whether this machine wants it running. Expensive payload stays a manifest tool list; config a program discovers by path and cannot branch on (hyprland, waybar, ghostty) stays a coordinate variant under `configs/`
- **Symlink Manager** - Deploys dotfiles from repo to home directory via `dotfiles symlinks apply`
- **Theme System** (`theme`) - Unified theming from one palette per theme. It installs each app config under the theme's own id and points a stable `current` symlink at it, so this repo's configs name `current` and never a theme — `rg -l --hidden '/current\b' configs/` finds the pointers — `--hidden` is load-bearing, since every one of them is under a `.config` directory — and `~/tools/theme/CLAUDE.md` § "Where an applied theme lands" says why the pointer keeps that name
- **Task Automation** - Modular Taskfile system for builds, tests, installations
- **Pre-commit Hooks** - Quality control. The inventory is generated, so read `.pre-commit-config.yaml` rather than a list here — a restated inventory goes stale on the next regeneration

**Symlink Management Critical Rule**:

After adding, removing or renaming any file under `configs/`, `apps/` or `shell/`, run `dotfiles symlinks apply`. One verb reconciles the whole declaration, so there is no create-only verb to pick between, and it is idempotent. What it prunes is not the same on every machine — `docs/reference/tools/symlinks.md` is the account, and a machine deploying by copy has no provenance to prune by. It deliberately does **not** unlink everything first: that gave a daemon watching its own config — Hyprland — a window to find the file gone and write itself a default, which the create pass then refused. Never reinstate a remove-everything pass. The window is closed by deciding per link rather than by ordering two passes — a link already deployed produces no change at all, so nothing unlinks it, and the prune set only ever holds links whose source is gone. `tests/resources/test_symlinks.py::test_a_deployed_config_is_never_touched_by_a_later_run` pins it.

`task relink` is equivalent but only works from inside the repo.

Common symptoms of outdated symlinks: "module not found" errors in Neovim, configs not being picked up, files in repo but not accessible in expected locations, or broken symlinks pointing at deleted repo files.

**The Checked-Out Branch Is Deployed Machine State** (⚠️ MANDATORY, unique to this repo):

`configs/`, `shell/` and `apps/` are symlinked live into `$HOME`, and the `dotfiles` CLI is
installed **editable** against `src/` (`~/.local/share/uv/tools/dotfiles/.../dotfiles.pth` points
at `~/dotfiles/src`). Switching branches therefore changes both the config this machine runs and
the tool that deploys it — a coupling almost no other repo has, and one nothing announces.

- **Every change here starts in a worktree, without checking for peers first.** `worktree new
  <slug>` is the first tool call, before reading files. This is the one repo where the usual
  size rule — small work commits straight to the main branch — does not decide it, because
  the cost of being on the wrong branch is not a lost commit but a machine running that branch —
  the coupling above. The check for a peer session costs a `ListAgents` call and gets skipped;
  the worktree costs seconds and never does. `worktree land` catches this checkout back up
  afterwards, which here is a redeploy rather than a formality.
- **`~/dotfiles` itself stays on `main`.** The primary checkout is deployed state, so a branch
  belongs in a worktree rather than checked out over the machine.
- **`EnterWorktree(path=…)` is what moves a session in**, and it refuses when the session's
  directory is not inside the owning repo — a session launched from `~/dev` cannot enter one at
  all. Drive it by absolute path from there; the isolated index is the part that matters.
- **One worktree per stack, at its top.** A stacked branch checked out in a second worktree is
  skipped silently by `rebase.updateRefs`, leaving that ref on pre-rebase commits.
- **Always run `dotfiles` from `~/dotfiles`, never from inside a worktree.** `DOTFILES_DIR` is
  exported in `.zshenv` to make the safe answer the default, but a shell that predates it, or one
  that overrides it, would resolve the repo root by walking up from the CWD and deploy the
  worktree's config over the machine's. A session that entered its worktree with `EnterWorktree`
  is inside one for every command it runs, so `cd ~/dotfiles &&` is the prefix that keeps an apply
  pointed at the machine rather than at the branch.
- **To exercise the worktree's own code against the real machine**, run it from inside the
  worktree with the machine's root passed in: `DOTFILES_DIR=/home/chris/dotfiles uv run --quiet
  dotfiles <cmd>`. That measures the machine while running the branch's logic, which is the
  combination the bullet above otherwise rules out.
- **A `uv run` inside a worktree leaves a `.venv` there**, which the packages resource then
  reports as undeclared binaries. That is the harness, not a finding — do not chase it.
- What to run to verify a change is `tests/README.md`. The levels and their costs are declared in
  `tests/e2e/levels.py` and the roster is `task --list-all | rg test:`; neither is restated here
  or anywhere else, because a copy is the thing that goes stale.
- `dotfiles check` and both apply paths warn when the checkout is off `main`
  (`checkout.stray_branch`). It is a warning, not a refusal — being on a branch here is a
  legitimate deliberate act, and the failure being guarded against is not knowing.

Measured 2026-08-09: four commits sat on `main` while a feature branch was checked out, so the
machine ran older tmux and gh-dash config, kept a deleted app, lacked two new ones, and had a
dangling wireplumber config — with nothing reporting any of it.

## Documentation Philosophy

Documentation in this repository serves as a technical reference for future me (6+ months later) and follows these principles:

**Structure** (inspired by CodeCompanion.nvim docs):

```text
docs/
├── apps/                # Per-tool: why it exists, what it deliberately doesn't do
├── architecture/        # HOW and WHY the system works
├── configuration/       # Per-program config decisions (docker, hyprland)
├── development/         # Testing and contributing
├── reference/           # Platform differences, symlinks, tasks, troubleshooting
└── learnings/           # Debugging artifacts, searched by symptom
```

General technical notes that do not name something in this repo belong on the
hub (`~/docs`), not here.

**Writing Guidelines**:

- ALWAYS write in the imperative tone.
  - Good: "Copy the config file"
  - Bad: "You should copy the config file"
  - Bad: "Now you can copy the config file"
- Conversational paragraphs over bulleted lists - maintain context and reasoning
- Technical and factual, not promotional
- Add new docs to `mkdocs.yml` navigation

Lead with what and why, then link to the details. Never duplicate content that
has a canonical source elsewhere.

**Never write a list a command produces** (⚠️ MANDATORY):

The rule is `~/.claude/CLAUDE.md` § "A Count Is a Command, Not a Constant". The commands
that replace the lists this repo kept writing: `task --list-all`,
`packages list --section=<x>`, `doit kit list`, `eza -1 install/manifests/`,
`rg '^[a-z_]+\(\)' <lib>`, `<tool> --help`.

A doc earns its lines by explaining a decision, a rejected alternative, a
non-obvious constraint, or a measured tradeoff — the things the code cannot
state about itself. **If a section would be regenerated correctly by `--help`,
delete it.**

This is the repo-local application of the global rule "A Count Is a Command,
Not a Constant" in `~/.claude/CLAUDE.md`, and it exists because the alternative
was measured. `docs/development/docs-audit.md` is the record: what was found
wrong, the baseline to compare against, and the re-measure commands. Read it
before running another docs review, and add to it rather than editing it — it
is a dated snapshot and the only place here where enumerations are the content.
`docker.md`, `tmux-sessions.md` and `custom-installers.md` are the models to
imitate; the shared property is that nothing in them changes when code changes.

**A page never explains a mechanism the module docstring explains**:

A page that walks through a mechanism the module docstring already explains is two
sources for one subject, and they diverge. The instrument for finding one is `task
docs:duplication`, which ranks every page by six-word runs it shares with any
docstring under `src/dotfiles/`. The worked example is
`docs/development/docs-audit.md` § "Third pass", where four pages scoring between
529 and 613 came down to single digits.

`refcheck` runs as a pre-commit hook and validates `source`/`bash` targets in
markdown as well as shell, so a doc citing a moved file now fails the commit.
It is a backstop for paths only — nothing mechanical catches a stale flag
table, which is why the rule above is to not write one.

## Key Custom Tools

- **dotfiles** (`dotfiles`) — the front door, usable from any directory. Three reconcile verbs, Terraform-shaped: `plan` (what `apply` would change), `apply`, and `check` (what is *wrong*, which a machine merely behind on versions is not). All three sit at the top level and again under each resource; `dotfiles --help` lists them. See `docs/architecture/management-interface.md`
- **Symlinks Manager** — `dotfiles symlinks apply`
- **Theme** (`theme`) — unified theming; `theme list` names the themes and `ls ~/tools/theme/lib/generators/` the apps
- **tmux Sessions** (`tmux-sessions`) — session switching, creation, and the cross-session window finder behind the two-line status bar. See `docs/architecture/tmux-sessions.md`
- **Task** — `task --list-all` from inside the repo; nearly every task is a thin `uv run dotfiles ...` onto `src/dotfiles/`, so both front doors reach one implementation

## Learnings Directory

**Search the learnings before diagnosing anything** (⚠️ MANDATORY):

Before investigating a failing install, a tool that stopped working, or an error that makes no sense, search `docs/learnings/` — by the symptom, not only by the tool:

```bash
rg -i "no route to host" docs/learnings/
rg -il "cifs|mount" docs/learnings/
```

The directory is browse-only in the mkdocs sidebar and nothing surfaces it at the moment something breaks, so it is consulted only if searching it is a deliberate first step. Skipping it cost a whole session re-diagnosing a WSL mount whose real cause was a package that had been installed by hand on the old distro and never declared anywhere.

**Quote the error verbatim** in every learning. The literal string a tool prints is what gets searched at the only moment the document matters; a learning that paraphrases its error is unfindable.

Document critical lessons in `docs/learnings/descriptive-name.md` (30-50 lines max). Add to `mkdocs.yml` navigation. Format: Problem → Solution → Key Learnings (actionable bullets).

- todo.md is for creating future work items, not to be used for planning, moved to .planning, or changed in any way
