# shellcheck shell=bash
# shellcheck disable=all
# zsh completion syntax (compdef, ${(@f)}) is not valid bash, and this file is
# sourced by .zshrc rather than executed — hence no shebang, like its siblings.
#
# Hand-written zsh completions for the apps that generate none of their own.
#
# Everything with a completion generator (cobra, Typer, gh, task) is wired up in
# .zshrc via cache_eval instead. This file is for the bash apps, where the
# completion has to be written by hand.
#
# Sourced after compinit, so `compdef` exists by the time these run.

# Pursuit names for `menu log` / `menu next skip`, read from the flat cache file
# menu-next rewrites on every run.
#
# Reading a file rather than asking the tool is the whole point: menu-next is a
# `uv run --script`, and a ~100ms interpreter start on every Tab is long enough
# to feel like the shell has hung.
_menu_pursuits() {
  local cache="${XDG_CACHE_HOME:-$HOME/.cache}/menu/next-names.txt"
  [[ -r $cache ]] || return 1
  local -a pursuits
  # name<TAB>description in the file, name:description for _describe.
  pursuits=("${(@f)$(<$cache)}")
  pursuits=("${(@)pursuits//$'\t'/:}")
  _describe -t pursuits 'pursuit' pursuits
}

_menu() {
  local -a verbs next_verbs
  verbs=(
    'next:What to do now, drawn from your weighted pursuits'
    'log:Record having done a pursuit'
    'dashboard:Everything outstanding across your apps, in lanes'
    'review:What is due to revisit'
    'labs:Hands-on practice that is due now'
    'find:Search across tools, workflows, skills, funcs, aliases'
    'help:Show help'
  )
  next_verbs=(
    'list:Every pursuit, its weight and implied share'
    'log:Record having done a pursuit'
    'skip:Pass on one — suppressed, weight untouched'
    'drift:Stated weight against what you actually did'
    'dormant:Pursuits gone colder than their weight implies'
    'edit:Edit the pursuits file'
  )

  if (( CURRENT == 2 )); then
    _describe -t commands 'menu command' verbs
    return
  fi

  case $words[2] in
    log)
      (( CURRENT == 3 )) && _menu_pursuits
      ;;
    next)
      if (( CURRENT == 3 )); then
        _describe -t commands 'menu next verb' next_verbs
      elif (( CURRENT == 4 )) && [[ $words[3] == (log|skip|pass) ]]; then
        _menu_pursuits
      fi
      ;;
  esac
}

compdef _menu menu
