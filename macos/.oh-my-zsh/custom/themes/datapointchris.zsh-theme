# ============================================================== #
# -------------------- DataPointChris Theme -------------------- #
#                                                                #
# -------      https://www.github.com/datapointchris      ------ #
# ============================================================== #

# --> Based off of SOBOLE Theme <--
# Author: Nikita Sobolev, github.com/sobolevn
# License: WTFPL
# https://github.com/sobolevn/sobole-zsh-theme

# `spectrum_ls` -> get a list of the color codes available
# Set color with `$fg[###]`

# =============================================== #
# ------------------ PROMPT --------------------- #
# =============================================== #
PROMPT='
$(current_venv) $(user_info):$(current_dir)  $(vcs_prompt_info)
$(current_caret) '
PROMPT2='. '
RPROMPT='%{$(echotc UP 1)%} $(vcs_status) ${_return_status}%{$(echotc DO 1)%}'
_return_status="%(?..%{$fg[red]%}%? ⚠️%{$reset_color%})"

# ---------- current_venv ---------- #
# Disable the standard prompt:
export VIRTUAL_ENV_DISABLE_PROMPT=1

function current_venv {
  if [[ ! -z "$VIRTUAL_ENV" ]]; then
    # Show this info only if virtualenv is activated:
    local dir=$(basename "$VIRTUAL_ENV")
    echo "%{$fg[yellow]%}($dir)%{$reset_color%}"
  fi
}

# ---------- user_info ---------- #
function user_info {
  # Shows user in the PROMPT if different from `$USER`
  # 'red' for root, blue for other users, teal for ssh
  if [[ -n $SSH_CONNECTION ]]; then
    if [[ "$USER" == "root" ]]; then
      echo "%{$fg[red]%}$USER@%m%{$reset_color%}"
    else
      echo "%{$fg[magenta]%}$USER@%m%{$reset_color%}"
    fi
  elif [[ "$USER" == "root" ]]; then
    echo "%{$fg[red]%}$USER@%m%{$reset_color%}"
  else
    echo "%{$FG[004]%}$USER@%m%{$reset_color%}"
  fi
}

# ---------- current_dir ---------- #
function current_dir {
  # Settings up current directory and settings max width for it:
  local _max_pwd_length="65"
  local color
  color="white"

  if [[ $(echo -n $PWD | wc -c) -gt ${_max_pwd_length} ]]; then
    echo "%{$fg_bold[$color]%}%-2~ ... %3~%{$reset_color%}"
  else
    echo "%{$fg_bold[$color]%}%~%{$reset_color%}"
  fi
}

# ---------- vcs_prompt_info ---------- #
function vcs_prompt_info {
  git_prompt_info
}

function vcs_status {
  git_prompt_status
}

# ---------- current_caret ---------- #
function current_caret {
  # This function sets caret color and sign
  # based on theme and privileges.
  if [[ "$USER" == "root" ]]; then
    CARET_COLOR="red"
    CARET_SIGN="$ ➜"
  else
    CARET_COLOR="green"
    CARET_SIGN="➜"
  fi

  echo "%{$fg[$CARET_COLOR]%}$CARET_SIGN%{$reset_color%}"
}


# ====================================================== #
# -------------------- Git Colors -------------------- #
# ====================================================== #
ZSH_THEME_GIT_PROMPT_PREFIX="%{$fg[green]%}"
ZSH_THEME_GIT_PROMPT_SUFFIX="%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_DIRTY=" %{$fg[red]%}✗%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_CLEAN=" %{$fg[green]%}✔%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_UNMERGED="%{$fg[cyan]%}§%{$reset_color%}"
ZSH_THEME_GIT_PROMPT_ADDED="%{$fg[green]%}✚%{$reset_color%}"


# ===================================================== #
# -------------------- `LS` Colors -------------------- #
# ===================================================== #
# Made with: http://geoff.greer.fm/lscolors/
export LSCOLORS="gxfxcxdxbxegedabagacad"
export LS_COLORS="di=36:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43"
# Turn on colors with default unix `ls` command:
export CLICOLOR=1


# ======================================================= #
# -------------------- `GREP` Colors -------------------- #
# ======================================================= #
export GREP_COLORS='mt40;93'
# export GREP_COLOR='40;93'


# ========================================================= #
# -------------------- `ZSTYLE` Colors -------------------- #
# ========================================================= #
# Internal zsh styles: completions, suggestions, etc
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%B--- %d%b"
