# Troubleshooting

## Start here

```sh
dotfiles plan        # symlink health and package-manifest drift
dotfiles packages check   # declared in packages.yml but not installed
toolbox check        # registry vs PATH vs disk
```

Between them these answer most of "why isn't this working", and they answer it
against the current state rather than against a guess. Run them before reading
further.

Also search the learnings by **symptom**, not by tool — the error string is what
was recorded:

```sh
rg -i "no route to host" docs/learnings/
```

## Command not found after installing

Check where the shell is actually looking:

```sh
echo $PATH | tr ':' '\n'
```

If the directory is missing, the shell has not been reloaded (`exec zsh`) or the
entry was added to the wrong end of `.zshrc` — `add_path` prepends, so the last
call wins. See
[Package Management](../../architecture/package-management.md#installation-location-strategy).

## Config changes not taking effect

A config that is not a symlink into the repo is a copy, and editing the repo
does nothing:

```sh
eza -l ~/.config/zsh/.zshrc   # should point into ~/dotfiles
dotfiles symlinks apply       # prunes dangling links and recreates all of them
```

`apply` prunes the links a deletion left dangling and then recreates every
declared one. It never unlinks everything first: that gave a daemon watching its
own config a window to find the file gone and write itself a default. It is
idempotent, and it is the only deployment verb — there is no create-only pass to
pick between.

## ZDOTDIR

The system file differs by distro, which is the part that catches people:
`/etc/zshenv` on macOS and Arch, `/etc/zsh/zshenv` on Ubuntu and WSL. Either
way it should contain `export ZDOTDIR="$HOME/.config/zsh"`. `dotfiles apply`
writes it on every platform, so a missing one means the apply did not finish —
or was never run, the bootstrap having only installed the CLI.

There is deliberately no `~/.zshenv` or `~/.zprofile`; see
[Architecture](../../architecture/index.md).

## Neovim

```sh
nvim -c "Lazy sync" -c "qa"        # force plugin sync
rm -rf ~/.local/share/nvim/lazy/   # clear the plugin cache and re-sync
:checkhealth vim.lsp               # from inside nvim, for LSP problems
```

A "module not found" error immediately after a repo change is usually a stale
symlink rather than a plugin problem — run `dotfiles symlinks apply` first.

## Theme

```sh
theme verify     # checks the theme system end to end
theme current
```

Ghostty needs a full restart for some changes; see
[Ghostty Shader Reload](../../learnings/ghostty-shader-reload.md).
