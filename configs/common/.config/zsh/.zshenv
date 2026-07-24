# shellcheck shell=bash
# Minimal PATH for non-interactive shells (SSH commands, cron, scripts).
# Full PATH setup with logging and platform branching is in .zshrc.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/bin:$PATH"

# SSH sessions inherit no locale (no SendEnv/AcceptEnv), leaving LC_CTYPE=C,
# where zsh's $'\uXXXX' escapes fail with "character not in range".
export LANG="${LANG:-en_US.UTF-8}"
