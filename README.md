# Dotfiles

Cross-platform dotfiles that work across macOS, WSL Ubuntu, and Arch Linux. Because maintaining three separate configs is nobody's idea of a good time.

## What This Is

A dotfiles setup that prioritizes shared configuration, with a per-coordinate directory only where a machine genuinely needs a different file. Includes a bunch of modern CLI tools, a theme system that actually works, and some custom tools to keep everything organized.

Shared zsh/tmux/neovim configs, automated theme switching, and a discovery system (`doit`) so you can actually remember what you installed.

## Quick Start

Clone, bootstrap the CLI with a machine manifest, then converge the machine:

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash install.sh --machine archlinux-personal-workstation
dotfiles apply --machine archlinux-personal-workstation
```

`install.sh` only puts uv and the `dotfiles` CLI on the box and prints those two
commands back; `dotfiles plan` says what `apply` would change before it changes
anything.

The manifests this checkout carries are the files in `install/manifests/`, and
`./install.sh --help` says what the bootstrap does. Once the CLI is on the box,
`dotfiles machines list` names them and `dotfiles machines show <name>` says
what one declares. `--machine` is required, but `MACHINE` in the environment
substitutes for it — and every converged machine exports one, so a bare
`./install.sh` there skips straight to reinstalling the CLI from whichever
checkout the script sits in.

A blocked download does not stop the run — the common case behind a corporate
firewall. `apply` names what failed when it ends, and `dotfiles report latest`
re-reads that run afterwards.

See the [full documentation](https://datapointchris.github.io/dotfiles/) for details.

## Structure

`configs/`, `apps/`, and `shell/` all follow the same pattern: a `common/` base beside `<axis>/<value>/` directories, where the axes are the six a machine varies along (`src/dotfiles/coordinates.py`). They mean opposite things by it — `shell/` holds **layers** and sources every one a machine selects, while `configs/` and `apps/` hold **variants** and exactly one file arrives. `eza -1 -D configs apps shell` shows which directories exist, and most do not — an axis earns one only where something actually differs along it. `install/` handles provisioning — machine manifests in `install/manifests/`, shared libraries in `install/common/`, and package definitions in `install/packages.yml`.

**External tools** (installed from GitHub, not in this repo):

- `doit`: Python app via `uv tool install git+https://github.com/datapointchris/doit`
- `theme`, `font`: Bash tools cloned to `~/.local/share/`

The core rule: a deployed path lives in exactly one directory. `declared()` in `src/dotfiles/resources/symlinks.py` walks each coordinate directory and appends without deduplicating, so the same relative path in `common/` and a coordinate directory is a collision producing two links at one target — never an override. There is no merge step, which is why a config that differs on one coordinate moves out of `common/` whole rather than being patched on top of it.

## Dotfiles Philosophy

This setup follows some opinionated principles that make maintenance easier:

**Nothing Is Detected**: a manifest declares where a machine sits on each of the six axes in `src/dotfiles/coordinates.py`, and `dotfiles env apply` writes them into `~/.env` for every shell and layer to read. OS detection was the earlier design and it could not answer the questions that actually decide a config — whether a box is on a trusted network, or whether it is meant to be a workstation or a server.

**Fail Fast in the Provider, Keep Going in the Engine**: a provider returns a result rather than raising, so one blocked download costs that row and nothing else. `src/dotfiles/engine.py` turns a provider that does raise into a refusal and finishes the plan. You get the full error context for what broke AND a working system with just a few missing pieces.

**Linear and Predictable**: stages run in the order `src/dotfiles/plan.py` declares, and `--through STAGE` stops part way. Ordering is a property of the work rather than of a command, which is why it lives on the stage and not on either resource it constrains.

**Reconcile, Don't Script**: `plan` says what `apply` would change, `apply` changes it, and `check` reports what is *wrong* — which a machine merely behind on versions is not. `dotfiles --help` shows where those three verbs sit.

This means when something breaks (and it will), you can quickly find and fix it. When you come back six months later, the code still makes sense.

## Visual Formatting and Emoji

Scripts in this repo use colors, unicode characters, and emojis to make output scannable and easy to understand at a glance.

**Default Assumption**: Output is for human consumption, not log aggregation systems. Readability trumps machine parsability.

**Color-Coded Hierarchy**:

- **Blue** thick borders (━━━): Main headers and footers
- **Cyan** text: Section headings and subsections
- **Green**: Success messages and status
- **Red**: Errors and failures
- **Yellow**: Warnings and cautions

**Status Indicators**:

- `✓` Unicode checkmarks for individual successes (keeps output compact)
- `✅` Emoji checkbox for final success messages (high visibility)
- `✗` Red X for errors
- `⚠️` Warning sign for important notes
- `•` Bullets for lists (cleaner than hyphens)

**Guidelines**:

- Use emojis sparingly but helpfully
- If there would be 50+ checkboxes, use unicode `✓` instead
- Never use decorative emojis (smileys, celebrations, etc.)
- Add spacing around major sections for breathing room

If a specific project's logs will be ingested by a log aggregation system (Splunk, ELK, etc.), dial back the colors and special characters. But that's rare for personal projects.

See `configs/common/.local/shell/formatting.sh` and `configs/common/.local/shell/colors.sh` for reusable libraries that are sourced system-wide and can be copied to other projects.

## Package Management

This setup uses different package managers for different purposes, because that's apparently the world we live in:

| What | How | Examples |
| --- | --- | --- |
| System utilities | brew / apt / pacman | ripgrep, tmux, zsh, jq |
| Rust CLI tools | cargo-binstall | bat, eza, fd, broot, git-delta |
| Editor / binaries | GitHub releases | neovim, lazygit, yazi, fzf |
| Python | uv | version management, ruff, mypy, etc. |
| Node.js | fnm | runtime, LSPs, formatters |

Why the split? Cross-platform consistency, project-specific versions, and keeping system packages separate from development tools.

See [CLAUDE.md](CLAUDE.md) for the full philosophy (it's longer than it needs to be, but comprehensive).

## Tool Discovery

Installed something six months ago and forgot about it? `doit` has you covered:

```bash
doit kit list             # See everything, every collection
doit show ripgrep         # Details, examples, why you installed it
doit find git             # Find git-related tools, cards and shortcuts
doit kit remind           # Surface something you forgot existed
doit kit unused           # What you own, can run, and never do
```

Tools are documented with usage examples and tips in the `terminal-library` registry, which `doit content sync` keeps current. It is authored content rather than machine config, so it lives in its own repo and changing it needs no deploy.

## Common Tasks

```bash
# Themes
theme list                              # List available themes
theme apply rose-pine                   # Apply theme across terminal apps

# Updates
dotfiles update                         # Pull the repo and repair what the pull invalidated
task update                             # Alias for install: apply is the update
dotfiles apply --owner datapointchris   # Only my own tools
dotfiles apply --reinstall --package lazygit  # Install one entry again, whatever it measures

# Symlinks
dotfiles symlinks apply                 # Deploy configs (also: plan, check, show, unlink)

# Discovery
doit find python                        # Find Python tools
```

Run `dotfiles` for all commands, or `task --list-all` when working inside the repo.

## Symlink Management

`dotfiles symlinks` deploys configs from the repo to their actual locations. Written in Python because shell scripts for path manipulation are a recipe for sadness.

**Important**: After adding or removing files in the repo, run `dotfiles symlinks apply` to update symlinks. Otherwise Neovim will complain about missing modules and you'll spend 20 minutes debugging before remembering this note.

## Theme System

One `theme.yml` palette per theme generates every app's colors, so ghostty, tmux, btop and Neovim cannot drift apart. `theme --help` is the command surface.

The generated config for each app lands under that theme's own id, with a stable `current` symlink pointed at it — which is why the configs in this repo name `current` and never a theme. The choice persists across sessions, and Neovim uses either a generated colorscheme or the theme's original plugin, whichever the theme declares.

## Documentation

Full docs are available at [datapointchris.github.io/dotfiles](https://datapointchris.github.io/dotfiles):

- [Architecture](https://datapointchris.github.io/dotfiles/architecture/) - How everything fits together
- [Reference](https://datapointchris.github.io/dotfiles/reference/) - Platforms, tools, fonts
- [Troubleshooting](https://datapointchris.github.io/dotfiles/reference/support/troubleshooting/) - When things break

There's also a [learnings](https://datapointchris.github.io/dotfiles/learnings/) section with extracted wisdom from bugs I've fixed and things I've figured out.

## Some Highlights

**Neovim**: Native LSP — one file per server in `configs/common/.config/nvim/lsp/`, which `eza -1` will list — plus CodeCompanion for Claude integration and a custom colorscheme manager spanning generated and plugin themes.

**Shell**: Custom ZSH prompt with git status, zoxide for smart directory jumping, fzf with preview, syntax highlighting, vi-mode.

**Modern CLI replacements**: bat (cat with syntax highlighting), eza (ls with git integration), fd (find that respects .gitignore), ripgrep (grep but faster), yazi (terminal file manager).

**Task automation**: one `Taskfile.yml` of namespaced entry points, listed by `task --list-all`. Both front doors reach the same place — nearly every task is a thin `uv run dotfiles ...` onto `src/dotfiles/`, so there is no second implementation to drift. `install/ops/docs.sh` is residue of an earlier split, not the mechanism.

## Contributing

This is a personal dotfiles repo, but you're welcome to:

- Steal ideas for your own setup
- Open issues if you spot something broken
- Suggest tools or improvements

## License

MIT - do whatever you want with it

---

**Tip**: `doit kit remind` surfaces something you have not reached for in 90 days, and the weekly nudge runs it for you.
