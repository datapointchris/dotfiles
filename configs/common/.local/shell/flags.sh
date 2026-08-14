#!/usr/bin/env bash
# ================================================================
# Feature Flag Library
# ================================================================
# One truthy test for every on/off switch in the fleet, so a flag reads the
# same whether it is checked from .zshrc, an installer, or an app.
#
# The model is load-everywhere, flag-decides: code ships to every machine and
# ~/.env says what that machine actually wants running. A machine whose ~/.env
# predates a flag therefore keeps the feature on rather than silently losing it
# — pass an explicit default of 0 for anything that should start life off.
#
# Declared flags and their per-machine defaults live in install/flags.yml;
# `dotfiles env apply` renders them into ~/.env. This library only answers the
# question, it does not own the list.
#
# Usage:
#   source "$HOME/.local/shell/flags.sh"
#   flag_enabled SHELL_NUDGE      && doit shell init zsh # unset => on
#   flag_enabled ZSHRC_DEBUG 0    && print_timings       # unset => off
# ================================================================

# Note: Libraries that are sourced should not set shell options.

# Classify a literal as on (0), off (1), or unrecognized (2).
#
# Character classes rather than a case-folded compare: this file is sourced by
# both zsh and bash, and the lowercase modifiers are not portable between them
# (${v:l} is zsh-only, ${v,,} is bash-only). Folding via tr would fork a
# subshell on every check, which .zshrc runs many times per startup.
flag_classify() {
  case "$1" in
    1 | [Tt][Rr][Uu][Ee] | [Yy][Ee][Ss] | [Oo][Nn]) return 0 ;;
    0 | [Ff][Aa][Ll][Ss][Ee] | [Nn][Oo] | [Oo][Ff][Ff]) return 1 ;;
    *) return 2 ;;
  esac
}

# flag_enabled NAME [default]
#   Returns 0 (enabled) or 1 (disabled). `default` applies when NAME is unset,
#   empty, or holds an unrecognized value; it defaults to 1 (enabled). An
#   unrecognized value is deliberately not guessed at — `dotfiles doctor`
#   reports it instead.
flag_enabled() {
  local name="$1"
  local default="${2:-1}"
  local value

  # eval rather than ${!name} / ${(P)name}: neither indirection form works in
  # both shells. The name is pattern-checked first so this cannot expand to
  # arbitrary code.
  case "$name" in
    [A-Za-z_]*) eval "value=\${$name-}" ;;
    *) value="" ;;
  esac

  flag_classify "$value"
  case $? in
    0) return 0 ;;
    1) return 1 ;;
  esac

  # An unrecognized default is a caller bug; normalize it to disabled rather
  # than letting flag_classify's 2 leak out as the return code.
  flag_classify "$default"
  case $? in
    0) return 0 ;;
    *) return 1 ;;
  esac
}

# ================================================================
# End of Feature Flag Library
# ================================================================
