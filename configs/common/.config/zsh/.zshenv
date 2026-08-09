# shellcheck shell=bash
# Minimal PATH for non-interactive shells (SSH commands, cron, scripts).
# Full PATH setup with logging and platform branching is in .zshrc.
#
# fnm's default alias comes first so bare `node` is the fleet version rather
# than whatever brew last upgraded to. It has to be here and not in .zshrc:
# pre-commit hooks, agents and scripts run non-interactive, and that is exactly
# where the wrong node bites — ichrisbirch pins 24 and its vitest suite fails
# outright on 26. --use-on-cd in .zshrc handles per-directory overrides on top.
export PATH="$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/share/npm/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/bin:$PATH"

# SSH sessions inherit no locale (no SendEnv/AcceptEnv), leaving LC_CTYPE=C,
# where zsh's $'\uXXXX' escapes fail with "character not in range".
export LANG="${LANG:-en_US.UTF-8}"

# The checkout every script and the CLI deploy from. Here and not in ~/.env for
# the same reason as fnm above: ~/.env is sourced from .zshrc, so it reaches
# interactive shells only. `paths.py` prefers this over walking up from its own
# file, and that walk is what makes it matter — run `dotfiles symlinks apply`
# from inside a git worktree with this unset and it deploys the worktree's
# config over the machine's.
export DOTFILES_DIR="$HOME/dotfiles"
