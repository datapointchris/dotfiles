# shellcheck shell=bash
# Minimal PATH for non-interactive shells (SSH commands, cron, scripts).
# Full PATH setup with logging and platform branching is in .zshrc.
#
# fnm's default alias comes first so bare `node` is the fleet version rather
# than whatever brew last upgraded to. It has to be here and not in .zshrc:
# pre-commit hooks, agents and scripts run non-interactive, and that is exactly
# where the wrong node bites — ichrisbirch pins 24 and its vitest suite fails
# outright on 26. --use-on-cd in .zshrc handles per-directory overrides on top.
#
# /usr/local/go/bin is the Go toolchain itself, and it belongs here rather than
# only in .zshrc for the same reason as fnm. It was in neither file on macOS, so
# `go` was on no PATH this machine has: gopls failed to load every Go workspace,
# and `dotfiles check` reported all 18 declared Go tools unmeasurable because
# nothing could run `go version -m` to read them.
#
# Held to toolchain.TOOL_PATH_DIRS by tests/cli/test_apply.py, which is the only
# thing that stops this line and that tuple drifting apart again.
export PATH="$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/share/npm/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/go/bin:/usr/local/bin:$PATH"

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

# sops looks in ~/Library/Application Support on macOS, so a Mac decrypted nothing.
export SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/sops/age/keys.txt}"

# Claude Code's Bash tool runs bash rather than the login shell. The model writes
# bash, and two zsh defaults break it: an unquoted variable is not word-split, and
# a glob matching nothing aborts the command. Here and not in .zshrc because a
# tmux pane starts claude from non-interactive zsh. Below the PATH line, so a Mac
# resolves Homebrew's bash ahead of its own 3.2.
CLAUDE_CODE_SHELL="$(command -v bash)"
export CLAUDE_CODE_SHELL
