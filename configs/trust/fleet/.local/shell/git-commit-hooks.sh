#!/usr/bin/env bash
# What the commit hooks git runs from fleet.gitconfig ask about the commit just
# made, answered once. Sourced by record-git-commit and link-commit-to-slate-worklog.

# The short name of the repo origin names, where origin has a host. A test's
# fixture repo, with no origin or a file: one, has none, so a hook asking it acts
# on nothing there.
hosted_repo_name() {
  local origin
  origin=$(git remote get-url origin 2>/dev/null) || return 1
  [[ $origin == *:* && $origin != file:* ]] || return 1
  basename "$origin" .git
}

# Whether the hook run given these arguments follows a commit it made. post-commit
# passes none. post-merge passes 1 for a squash, which commits nothing. A
# fast-forward moves HEAD onto a commit that already existed, and git's reflog
# subject for it is untranslated in every locale. `worktree land` makes its merge
# with dotfiles.postMergeAfterPush set and runs post-merge again once the merge is
# pushed, so a merge a lost race drops is never recorded.
made_a_commit() {
  (($# == 0)) && return 0
  [[ $1 == 0 ]] || return 1
  [[ $(git config --type=bool --get dotfiles.postMergeAfterPush 2>/dev/null) != true ]] || return 1
  [[ $(git reflog -1 --format=%gs HEAD 2>/dev/null) != *': Fast-forward'* ]]
}

# The kind of agent the session is, as the git.commit_made record names it.
agent_name() {
  if [[ -n ${SLATE_ACTOR:-} ]]; then
    # The scheduler sets <job>@<machine>. The name leaves the machine out, because
    # the record's shipper adds host.name.
    echo "claude-code-unattended/${SLATE_ACTOR%@*}"
  elif [[ ${CLAUDE_CODE_SESSION_ATTENDED:-} == 0 ]]; then
    echo claude-code-unattended
  else
    local handle=''
    [[ -z ${TMUX_PANE:-} ]] || handle=$(tmux display-message -p -t "$TMUX_PANE" '#{@place_handle}' 2>/dev/null) || handle=''
    echo "claude-code${handle:+/$handle}"
  fi
}
