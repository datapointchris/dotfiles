# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

#@fad
#--> Git add modified files matching pattern
function fad() {
  if [ -z "$1" ]; then
    echo "Usage: fad <pattern>"
    echo "Example: fad init"
    return 1
  fi

  git status --short | grep -E '^ ?M' | awk '{print $2}' | grep -i "$1" | xargs -r git add
  git status --short | grep -E '^[AM]'
}

#@gdp
#--> Git diff preview for modified files
function gdp() {
  # shellcheck disable=SC2016
  git status --short | awk '{print $2}' | \
    fzf --preview 'git diff --color=always {} | delta --paging=never --width=$FZF_PREVIEW_COLUMNS' \
        --preview-window='up:85%' \
        --bind 'ctrl-d:preview-page-down,ctrl-u:preview-page-up'
}

#@adcomp
#--> Git add all, commit with message and push
function adcomp() {
  git add . && git commit -m "$1" && git push
}

#@gm
#--> Git commit with message
function gm() {
  git commit -m "$1"
}

#@git-old-branches
#--> Look for old branches that have been merged into master, --remote to check remote branches
function git-old-branches() {
  if [ "$1" = "--remote" ]; then
    option="-r"
  else
    option=""
  fi
  for k in $(git branch $option --format="%(refname:short)" --merged master); do
    if (($(git log -1 --since='1 month ago' -s "$k" | wc -l) == 0)); then
      echo "$k"
    fi
  done
}
