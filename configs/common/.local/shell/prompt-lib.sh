# shellcheck shell=bash
# ================================================================
# Shared Prompt Library
# ================================================================
# Common utilities for bash and zsh prompts.
# Sourced by prompt.bash and prompt.zsh
# ================================================================

# ================================================================
# NERD FONT ICONS
# ================================================================
# Export as variables for use in prompt scripts

# shellcheck disable=SC2034
PROMPT_ICON_BRANCH=$'\ue0a0'   # git branch
PROMPT_ICON_UNTRACKED="󱀶"      # question file
PROMPT_ICON_ADDED=$'\uf067'    # plus
PROMPT_ICON_MODIFIED=$'\uf459' # modified file
PROMPT_ICON_DELETED=$'\uf068'  # minus
PROMPT_ICON_RENAMED=$'\uf061'  # arrow right
PROMPT_ICON_UNMERGED=$'\uf071' # warning triangle
PROMPT_ICON_CLEAN=$'\uf00c'    # check mark
PROMPT_ICON_STASH=$'\uf01c'    # inbox/stash
PROMPT_ICON_UP=$'\uf062'       # up arrow
PROMPT_ICON_DOWN=$'\uf063'     # down arrow
PROMPT_ICON_CARET=$'\u276f'    # ❯ symbol

# ================================================================
# GIT UTILITIES
# ================================================================

# Read the whole git state in one call and publish it as variables the prompts
# read directly. Branch, upstream divergence, stash count and per-file status all
# come from a single `git status`, because each separate git invocation costs a
# process spawn: the previous five-function version ran seven of them per prompt
# and took ~78ms against ~18ms for this. --no-optional-locks keeps a prompt from
# taking the index lock and fighting a concurrent git command.
#
# Returns non-zero outside a repo, which is what callers branch on.
PROMPT_GIT_BRANCH=""
PROMPT_GIT_AHEAD=0
PROMPT_GIT_BEHIND=0
PROMPT_GIT_STASH=0
PROMPT_GIT_FLAGS=""

prompt_git_load_state() {
  PROMPT_GIT_BRANCH=""
  PROMPT_GIT_AHEAD=0
  PROMPT_GIT_BEHIND=0
  PROMPT_GIT_STASH=0
  PROMPT_GIT_FLAGS=""

  local out
  out=$(git --no-optional-locks status --porcelain=v2 --branch --show-stash 2>/dev/null) || return 1

  local line oid ab xy x y
  local untracked="" staged="" modified="" deleted="" renamed="" unmerged=""

  while IFS= read -r line; do
    case "$line" in
      '# branch.oid '*) oid="${line#\# branch.oid }" ;;
      '# branch.head '*) PROMPT_GIT_BRANCH="${line#\# branch.head }" ;;
      '# stash '*) PROMPT_GIT_STASH="${line#\# stash }" ;;
      '# branch.ab '*)
        ab="${line#\# branch.ab }"
        PROMPT_GIT_AHEAD="${ab%% *}"
        PROMPT_GIT_BEHIND="${ab##* }"
        PROMPT_GIT_AHEAD="${PROMPT_GIT_AHEAD#+}"
        PROMPT_GIT_BEHIND="${PROMPT_GIT_BEHIND#-}"
        ;;
      '? '*) untracked=1 ;;
      'u '*) unmerged=1 ;;
      # Ordinary (1) and renamed/copied (2) entries both carry XY at the same
      # offset: X is the staged change, Y the one in the working tree.
      '1 '* | '2 '*)
        xy="${line:2:2}"
        x="${xy:0:1}"
        y="${xy:1:1}"
        [[ "$x" == "A" ]] && staged=1
        [[ "$x" == "R" ]] && renamed=1
        [[ "$x" == "M" || "$y" == "M" ]] && modified=1
        [[ "$x" == "D" || "$y" == "D" ]] && deleted=1
        ;;
    esac
  done <<<"$out"

  # A detached HEAD reports "(detached)" as the branch; show the short SHA instead.
  [[ "$PROMPT_GIT_BRANCH" == "(detached)" ]] && PROMPT_GIT_BRANCH="${oid:0:7}"

  [[ $untracked ]] && PROMPT_GIT_FLAGS+="untracked "
  [[ $staged ]] && PROMPT_GIT_FLAGS+="staged "
  [[ $modified ]] && PROMPT_GIT_FLAGS+="modified "
  [[ $deleted ]] && PROMPT_GIT_FLAGS+="deleted "
  [[ $renamed ]] && PROMPT_GIT_FLAGS+="renamed "
  [[ $unmerged ]] && PROMPT_GIT_FLAGS+="unmerged "
  [[ -z "$PROMPT_GIT_FLAGS" ]] && PROMPT_GIT_FLAGS="clean"

  return 0
}

# ================================================================
# DIRECTORY UTILITIES
# ================================================================

# Truncate directory path (default 45 chars, first 2/.../last 2)
prompt_truncate_dir() {
  local max_length="${1:-45}"
  local pwd_display="${PWD/#$HOME/\~}"

  if [[ ${#pwd_display} -gt $max_length ]]; then
    local first last_dirs
    first=$(echo "$pwd_display" | cut -d'/' -f1-2)
    last_dirs=$(echo "$pwd_display" | rev | cut -d'/' -f1-2 | rev)
    pwd_display="${first}/.../${last_dirs}"
  fi

  echo "$pwd_display"
}

# ================================================================
# USER CONTEXT
# ================================================================

# Determine user context for prompt coloring
# Returns: "local", "ssh", "root", or "root-ssh"
prompt_user_context() {
  if [[ -n "$SSH_CONNECTION" ]]; then
    if [[ "$USER" == "root" ]]; then
      echo "root-ssh"
    else
      echo "ssh"
    fi
  elif [[ "$USER" == "root" ]]; then
    echo "root"
  else
    echo "local"
  fi
}

# ================================================================
# VIRTUALENV
# ================================================================

# The virtualenv's directory name, taken by parameter expansion rather than by
# forking basename. Both prompts call this once per redraw, so a fork here is a
# process per prompt to strip a path. `##*/` is POSIX and works on the bash 3.2
# macOS ships, so the rule stays in one place for both shells.
prompt_venv_name() {
  if [[ -n "$VIRTUAL_ENV" ]]; then
    printf '%s\n' "${VIRTUAL_ENV##*/}"
  fi
}
