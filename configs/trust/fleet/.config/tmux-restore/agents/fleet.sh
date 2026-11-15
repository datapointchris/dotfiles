# shellcheck shell=bash
# tmux-restore adapter for a Claude conversation a `fleet tui` board opened in its own terminal,
# such as the inbox's C. tmux-restore looks no deeper than a pane's child, where the board sits,
# so the board alone would come back. The saved command reopens the conversation first and starts
# the board again once it is quit, which is where quitting it led before.
#
# The conversation id and the flags to keep come from the claude adapter that tmux-restore ships
# and sources ahead of this file. A board with no conversation open is saved as it runs.

fleet_match() {
  [[ $(proc_comm "$1") == fleet ]] && proc_args "$1" && [[ ${ARGV[0]:-} == tui ]]
}

# fleet_conversation BOARD_PID: the claude the board handed its terminal to.
fleet_conversation() {
  local child
  for child in $(proc_children "$1"); do
    [[ $(proc_comm "$child") == claude ]] && printf '%s\n' "$child" && return 0
  done
  return 1
}

fleet_session() {
  local child
  child=$(fleet_conversation "$1") && claude_session "$child"
}

fleet_resume() {
  local child conversation
  child=$(fleet_conversation "$1") && conversation=$(claude_resume "$child" "$2") || return 1
  proc_args "$1" || return 1
  printf '%s; fleet' "$conversation"
  printf ' %q' "${ARGV[@]}"
}
