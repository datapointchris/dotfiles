# Troubleshooting

## Start here

```sh
dotfiles plan        # symlink health and package-manifest drift
dotfiles packages check   # declared in packages.yml but not installed
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
dotfiles symlinks apply       # reconcile every declared link
```

## ZDOTDIR lives in a different file per distribution

`ls /etc/zshenv /etc/zsh/zshenv` says which one this machine has; whichever it
is should contain `export ZDOTDIR="$HOME/.config/zsh"`. Reaching for the wrong
spelling is silent, because zsh reads the other and says nothing. `dotfiles apply`
writes it on every platform, so a missing one means the apply did not finish —
or was never run, the bootstrap having only installed the CLI.

There is deliberately no `~/.zshenv` or `~/.zprofile`; see
[Architecture](../../architecture/index.md).

## A Neovim "module not found" is a stale symlink, not a plugin problem

That is true whenever the error arrives immediately after a repo change. Run
`dotfiles symlinks apply` before touching anything in `lazy.nvim`.

## Ghostty needs a full restart for some theme changes

See [Ghostty Shader Reload](../../learnings/ghostty-shader-reload.md).
