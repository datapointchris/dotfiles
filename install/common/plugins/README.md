# Plugin Installers

Two scripts, and both are here because an external plugin manager owns the
installing.

`tmux-plugins.sh` runs TPM. `nvim-plugins.sh` runs `Lazy! sync`. In each case the
plugin list lives where that manager reads it — `@plugin` lines in `tmux.conf`,
a lua spec for Neovim — and not in `packages.yml`. There is no per-item
declaration, so there is nothing for the resolver to plan and nothing for
`dotfiles plugins check` to compare: it reports the *clones* and says as much.

The clones went to Python. `shell-plugins.sh` and `tpm.sh` each re-read
`packages.yml` through their own interpreter to ask which repos to clone into
which directory, which is a question the resolver already answers;
`src/dotfiles/resources/plugins.py` does the cloning now.

## Why `tmux-plugins.sh` is still shell

It is a sequence of `tmux` invocations with three safety properties that are
easy to lose and expensive to lose, all documented at the point they are set up:

- `TMUX_TMPDIR` puts the throwaway server on its own socket, because TPM shells
  out to a bare `tmux` and would otherwise install into the user's live server —
  where tmux-resurrect is free to snapshot the throwaway session.
- Every call additionally passes `-S` with that socket spelled out, because
  cleanup runs `kill-server`: one unset variable and that sentence ends at the
  user's live sessions.
- `$TMUX` is unset, because it names the live server's socket and outranks
  `TMUX_TMPDIR`.

It also sets `TMUX_PLUGIN_MANAGER_PATH` directly rather than relying on the tpm
bootstrap line in `tmux.conf` having set it on a running server. Relying on that
chain is what broke: a server already running from before the config was linked
leaves the variable unset and TPM aborts with "not configured in tmux.conf",
naming the one thing that is usually fine.

## Where the pieces are

Run `rg -l 'plugins' install/common/plugins/` for the scripts, and read
`src/dotfiles/resources/plugins.py` for the clones. `tests/install/integration/plugin-installers.bats`
covers the TPM run against a stub.
