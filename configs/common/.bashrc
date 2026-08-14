# shellcheck shell=bash
# shellcheck disable=SC1091

SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"

# Deployed by `dotfiles symlinks apply`, and sourced without testing for them.
# Whether they are there is the declaration's question, and `dotfiles symlinks
# check` answers it by name rather than by a path this file happened to try.
source "$SHELL_DIR/colors.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/functions.sh"
source "$SHELL_DIR/aliases.sh"
source "$SHELL_DIR/prompt.bash"

# Guarded, and deliberately: `~/.env` is written by `dotfiles env apply`, which
# runs after this file is deployed. A fresh box has a shell before it has this,
# and bootstrap ordering is not a fault to report.
[[ -f "$HOME/.env" ]] && source "$HOME/.env"

# The coordinate layers, read off the disk. `symlinks apply` deploys only the
# directories this machine's coordinates select and prunes the ones it no longer
# does, so this tree is the resolved answer — no list in `~/.env`, and nothing to
# fall out of step with it. nullglob keeps an unmatched pattern from arriving as
# a literal, which is bash's default and the reason the old loop tested -r.
shopt -s nullglob
for layer_file in "$SHELL_DIR"/*/*/*.sh; do
  source "$layer_file"
done
shopt -u nullglob
unset layer_file

# Machine-local file, after the layers so it can build on what they exported.
# Guarded where the layers above are not, and for the opposite reason: this one
# is declared in `install/flags.yml` and never deployed, because it holds shell
# code that deliberately stays out of this repo — employer hostnames and the
# like. safekeep restores it, so it is legitimately absent between an apply and
# that restore, and `dotfiles check` is what reports it rather than this line.
[[ -f "$SHELL_DIR/local.sh" ]] && source "$SHELL_DIR/local.sh"

# Guarded: rustup writes this, dotfiles never deploys it, so its absence says
# nothing about whether this machine is converged.
[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"

command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init bash)"
command -v fzf >/dev/null 2>&1 && eval "$(fzf --bash)"
