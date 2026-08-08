#!/usr/bin/env bash

# Phase registry, selection, and shared argument handling for install.sh and update.sh.
#
# Both commands walk the same registry in the same order and accept the same
# selectors; only the function a phase dispatches to differs. One registry is
# what stops the two surfaces drifting — before this, update took group names
# and install took nothing at all, and the phase names update printed under
# --list could not be selected on either.
#
# Set PHASE_VERB to "install" or "update" before sourcing.
#
# Format: name|group|owner_aware|install_fn|update_fn
#
# owner_aware marks a phase whose contents can be traced to a GitHub owner, and
# so can be narrowed by --mine. Phases driven by a registry instead (apt, npm,
# PyPI) have no owner, and are skipped under --mine rather than silently running
# in full.
#
# `-` for either function means the phase does not exist for that verb:
# symlinking and the zsh setup are deployment steps with nothing to update.
#
# Registry order is execution order, which is why the two config phases sit
# among the plugin phases: symlinks must land after the tools that provide
# `task` and before tpm reads the tmux config it deploys.

OWNER="datapointchris"

PHASE_GROUPS=(system languages tools config plugins)

PHASE_REGISTRY=(
  "system-packages|system|no|install_system_packages|update_system_packages"
  "go-toolchain|languages|no|install_go_toolchain|update_go_toolchain"
  "rust-toolchain|languages|no|install_rust_toolchain|update_rust_toolchain"
  "uv|languages|no|install_uv|update_uv"
  "go-tools|tools|yes|install_go_tools|update_go_tools"
  "github-releases|tools|yes|install_github_releases|update_github_releases"
  "custom-installers|tools|yes|install_custom_installers|update_custom_installers"
  "cargo|tools|yes|install_cargo_packages|update_cargo_packages"
  # Between cargo and npm-globals, not in the languages group: fnm ships as a
  # cargo package, and the globals must install against the Node this pins.
  "node-toolchain|tools|no|install_node_toolchain|update_node_toolchain"
  "npm-globals|tools|no|install_npm_globals|update_npm_globals"
  "uv-tools|tools|yes|install_uv_tools|update_uv_tools"
  "shell-plugins|plugins|no|install_shell_plugins|update_shell_plugins"
  "symlinks|config|no|install_symlinks|-"
  "tmux-plugins|plugins|no|install_tmux_plugins|update_tmux_plugins"
  "nvim-plugins|plugins|no|install_nvim_plugins|update_nvim_plugins"
  "system-config|config|no|install_system_config|-"
)

GROUPS_SELECTED=()
GROUPS_SKIPPED=()
PHASES_SELECTED=()
PHASES_SKIPPED=()
MINE=false
DRY_RUN=false

# ================================================================
# REGISTRY ACCESS
# ================================================================

# The function this phase dispatches to under the current verb, or "-" when the
# phase does not apply.
phase_function() {
  local entry="$1" install_fn update_fn
  IFS='|' read -r _ _ _ install_fn update_fn <<<"$entry"
  if [[ "$PHASE_VERB" == "install" ]]; then
    echo "$install_fn"
  else
    echo "$update_fn"
  fi
}

phase_applies() {
  [[ "$(phase_function "$1")" != "-" ]]
}

array_contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

# Verb-aware, like phase_name_is_valid: `update config` would otherwise be
# accepted and then select nothing, since both config phases are install-only.
group_is_valid() {
  local candidate="$1" entry group
  for entry in "${PHASE_REGISTRY[@]}"; do
    IFS='|' read -r _ group _ <<<"$entry"
    [[ "$group" == "$candidate" ]] && phase_applies "$entry" && return 0
  done
  return 1
}

# The groups with at least one phase under the current verb, for error output.
available_groups() {
  local group entry phase_group available=()
  for group in "${PHASE_GROUPS[@]}"; do
    for entry in "${PHASE_REGISTRY[@]}"; do
      IFS='|' read -r _ phase_group _ <<<"$entry"
      if [[ "$phase_group" == "$group" ]] && phase_applies "$entry"; then
        available+=("$group")
        break
      fi
    done
  done
  echo "${available[*]}"
}

# Only phases that exist for the current verb are selectable, so `update
# symlinks` fails loudly rather than silently matching nothing.
phase_name_is_valid() {
  local candidate="$1" entry name
  for entry in "${PHASE_REGISTRY[@]}"; do
    IFS='|' read -r name _ <<<"$entry"
    [[ "$name" == "$candidate" ]] && phase_applies "$entry" && return 0
  done
  return 1
}

selector_is_valid() {
  group_is_valid "$1" || phase_name_is_valid "$1"
}

# ================================================================
# SELECTION
# ================================================================

phase_selected() {
  local name="$1" group="$2" owner_aware="$3"
  local matched=false

  if [[ ${#GROUPS_SELECTED[@]} -gt 0 || ${#PHASES_SELECTED[@]} -gt 0 ]]; then
    if [[ ${#GROUPS_SELECTED[@]} -gt 0 ]] && array_contains "$group" "${GROUPS_SELECTED[@]}"; then
      matched=true
    fi
    if [[ ${#PHASES_SELECTED[@]} -gt 0 ]] && array_contains "$name" "${PHASES_SELECTED[@]}"; then
      matched=true
    fi
    [[ "$matched" == "true" ]] || return 1
  fi
  if [[ ${#GROUPS_SKIPPED[@]} -gt 0 ]] && array_contains "$group" "${GROUPS_SKIPPED[@]}"; then
    return 1
  fi
  if [[ ${#PHASES_SKIPPED[@]} -gt 0 ]] && array_contains "$name" "${PHASES_SKIPPED[@]}"; then
    return 1
  fi
  if [[ "$MINE" == "true" && "$owner_aware" != "yes" ]]; then
    return 1
  fi
  return 0
}

# Names of the phases the current selection resolves to, in registry order.
# main() and the unit tests both read the selection through this, so there is no
# second implementation to disagree with.
selected_phase_names() {
  local entry name group owner_aware
  for entry in "${PHASE_REGISTRY[@]}"; do
    IFS='|' read -r name group owner_aware _ <<<"$entry"
    phase_applies "$entry" || continue
    phase_selected "$name" "$group" "$owner_aware" && echo "$name"
  done
  return 0
}

# ================================================================
# DRY-RUN ITEM RESOLUTION
# ================================================================
# One definition per phase, shared by both verbs — the lists are the same
# packages.yml queries whichever way they are about to be acted on. Named for
# the phase rather than the function so neither verb owns them.

items_go_tools() {
  parse_packages --type=go --format=name_package | cut -d'|' -f1
}

items_github_releases() {
  parse_packages --type=github
}

items_custom_installers() {
  parse_packages --type=custom
}

items_cargo() {
  parse_packages --type=cargo --format=name_command | cut -d'|' -f1
}

items_npm_globals() {
  parse_packages --type=npm
}

items_uv_tools() {
  parse_packages --type=uv
  parse_packages --type=git_uv | cut -d'|' -f1
}

items_shell_plugins() {
  parse_packages --type=shell-plugins --format=names
}

run_phase() {
  local name="$1" group="$2" fn="$3"

  if [[ "$DRY_RUN" != "true" ]]; then
    "$fn"
    return $?
  fi

  print_section "$name ($group)"
  local items_fn="items_${name//-/_}"
  if declare -F "$items_fn" >/dev/null; then
    local items item
    items=$("$items_fn")
    if [[ -n "$items" ]]; then
      while IFS= read -r item; do
        echo "  $item"
      done <<<"$items"
    else
      log_warning "  nothing selected"
    fi
  fi
}

run_selected_phases() {
  local entry name group owner_aware fn ran=0
  for entry in "${PHASE_REGISTRY[@]}"; do
    IFS='|' read -r name group owner_aware _ <<<"$entry"
    phase_applies "$entry" || continue
    phase_selected "$name" "$group" "$owner_aware" || continue
    run_phase "$name" "$group" "$(phase_function "$entry")"
    ran=$((ran + 1))
  done

  if [[ $ran -eq 0 ]]; then
    log_warning "No phases selected"
    return 1
  fi
  return 0
}

# ================================================================
# SHARED ARGUMENTS
# ================================================================

list_phases() {
  local group entry name phase_group owner_aware shown
  help_header "$PHASE_VERB groups and phases"
  help_text "Any group or phase name below can be given as a positional selector."
  for group in "${PHASE_GROUPS[@]}"; do
    shown=false
    for entry in "${PHASE_REGISTRY[@]}"; do
      IFS='|' read -r name phase_group owner_aware _ <<<"$entry"
      [[ "$phase_group" != "$group" ]] && continue
      phase_applies "$entry" || continue
      [[ "$shown" == "false" ]] && help_section "$group" && shown=true
      if [[ "$owner_aware" == "yes" ]]; then
        help_row "$name" "" "(supports --mine)"
      else
        help_row "$name"
      fi
    done
  done
  help_end
  exit 0
}

reject_selector() {
  log_error "Unknown group or phase: $1"
  echo "Valid groups: $(available_groups)"
  echo "Run with --list to see every phase"
  exit 1
}

# Handles the selectors and flags common to both commands, reporting how many
# arguments it took through SHARED_ARG_CONSUMED. 0 means the caller must handle
# the argument itself, which is how install keeps --machine/--force/--offline
# without this library knowing about them.
#
# Through a variable rather than stdout because the invalid-selector paths exit:
# inside a command substitution that would only kill the subshell, and the run
# would carry on with the bad argument silently dropped.
export SHARED_ARG_CONSUMED=0

consume_shared_arg() {
  SHARED_ARG_CONSUMED=0
  case "$1" in
    --skip)
      if [[ -z "${2:-}" ]]; then
        log_error "--skip requires a group or phase name"
        exit 1
      fi
      if group_is_valid "$2"; then
        GROUPS_SKIPPED+=("$2")
      elif phase_name_is_valid "$2"; then
        PHASES_SKIPPED+=("$2")
      else
        reject_selector "$2"
      fi
      SHARED_ARG_CONSUMED=2
      ;;
    --no-system)
      GROUPS_SKIPPED+=("system")
      SHARED_ARG_CONSUMED=1
      ;;
    --mine)
      MINE=true
      SHARED_ARG_CONSUMED=1
      ;;
    --dry-run)
      DRY_RUN=true
      SHARED_ARG_CONSUMED=1
      ;;
    --list)
      list_phases
      ;;
    -*) ;;
    *)
      if group_is_valid "$1"; then
        GROUPS_SELECTED+=("$1")
      elif phase_name_is_valid "$1"; then
        PHASES_SELECTED+=("$1")
      else
        reject_selector "$1"
      fi
      SHARED_ARG_CONSUMED=1
      ;;
  esac
}

# The rows both commands print for the shared flags, so the two help screens
# cannot describe the same flag differently.
help_shared_options() {
  help_row "--skip" "NAME" "Skip a group or phase (repeatable)"
  help_row "--no-system" "" "Alias for --skip system"
  help_row "--mine" "" "Only tools owned by $OWNER; phases without an owner are skipped"
  help_row "--list" "" "Show every group and its phases"
  help_row "--dry-run" "" "Show what would run without running it"
}

# PACKAGE_OWNER is what package-query.sh turns into the --owner filter, and
# go-tools.sh and the other tool scripts read it from the environment when they
# build their own queries.
export_selection_environment() {
  if [[ "$MINE" == "true" ]]; then
    export PACKAGE_OWNER="$OWNER"
  fi
}
