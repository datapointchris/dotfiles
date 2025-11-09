#shellcheck disable=all
# ================================================================== #
# ZSH PROMPT CONFIGURATION
# ================================================================== #

# Enable parameter expansion, command substitution and arithmetic expansion in prompts
setopt PROMPT_SUBST

# Disable virtualenv prompt modification (Handled in custom prompt)
export VIRTUAL_ENV_DISABLE_PROMPT=1

# ========== Git utility functions ==========
function git_current_branch() {
    if git rev-parse --git-dir >/dev/null 2>&1; then
        git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null
    fi
}

function git_repo_check() {
    git rev-parse --git-dir >/dev/null 2>&1
}

function git_main_branch() {
    if git show-ref -q --verify refs/heads/main; then
        echo main
    else
        echo master
    fi
}

function git_develop_branch() {
    for branch in dev devel development develop; do
        if git show-ref -q --verify refs/heads/$branch; then
            echo $branch
            return
        fi
    done
    echo develop
}

# ========== Prompt component functions ==========

function aws_prompt_info() {
    # Skip if no AWS context is set
    if [[ -z "$AWS_PROFILE" && -z "$AWS_DEFAULT_REGION" && -z "$AWS_REGION" && -z "$AWS_ACCESS_KEY_ID" ]]; then
        return
    fi

    local aws_info=""
    local aws_symbol="$(echo -e '󰅠')"

    # Get AWS profile
    local profile="${AWS_PROFILE:-default}"

    # Get AWS region
    local region="${AWS_REGION:-${AWS_DEFAULT_REGION}}"

    # Check for credential expiration from various tools
    local expiration=""

    # Check aws-vault expiration
    if [[ -n "$AWS_SESSION_EXPIRATION" ]]; then
        # Parse the ISO 8601 timestamp - try multiple approaches
        local exp_time=""
        if command -v gdate >/dev/null 2>&1; then
            # Use GNU date if available (installed via brew)
            exp_time=$(gdate -d "$AWS_SESSION_EXPIRATION" +%s 2>/dev/null)
        elif date --version >/dev/null 2>&1; then
            # GNU date (Linux or GNU coreutils on macOS)
            exp_time=$(date -d "$AWS_SESSION_EXPIRATION" +%s 2>/dev/null)
        else
            # BSD date (native macOS)
            exp_time=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$AWS_SESSION_EXPIRATION" +%s 2>/dev/null)
        fi

        if [[ -n "$exp_time" ]]; then
            local current_time=$(date +%s)
            local time_diff=$((exp_time - current_time))
            if [[ $time_diff -gt 0 ]]; then
                local hours=$((time_diff / 3600))
                local minutes=$(((time_diff % 3600) / 60))
                expiration="$(printf '%dh%02dm' $hours $minutes)"
            else
                expiration="EXPIRED"
            fi
        fi
    fi

    # Check AWSume expiration
    if [[ -z "$expiration" && -n "$AWSUME_EXPIRATION" ]]; then
        # Parse the ISO 8601 timestamp - try multiple approaches
        local exp_time=""
        if command -v gdate >/dev/null 2>&1; then
            # Use GNU date if available (installed via brew)
            exp_time=$(gdate -d "$AWSUME_EXPIRATION" +%s 2>/dev/null)
        elif date --version >/dev/null 2>&1; then
            # GNU date (Linux or GNU coreutils on macOS)
            exp_time=$(date -d "$AWSUME_EXPIRATION" +%s 2>/dev/null)
        else
            # BSD date (native macOS)
            exp_time=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$AWSUME_EXPIRATION" +%s 2>/dev/null)
        fi

        if [[ -n "$exp_time" ]]; then
            local current_time=$(date +%s)
            local time_diff=$((exp_time - current_time))
            if [[ $time_diff -gt 0 ]]; then
                local hours=$((time_diff / 3600))
                local minutes=$(((time_diff % 3600) / 60))
                expiration="$(printf '%dh%02dm' $hours $minutes)"
            else
                expiration="EXPIRED"
            fi
        fi
    fi

    # Build the info string with symbol at front only
    aws_info=" %F{117}${aws_symbol} ${profile}"
    [[ -n "$region" ]] && aws_info="${aws_info}@${region}"
    if [[ -n "$expiration" ]]; then
        if [[ "$expiration" == *"EXPIRED"* ]]; then
            aws_info="${aws_info}%f %F{red}[${expiration}]%f"
        else
            aws_info="${aws_info}%f %F{green}[${expiration}]%f"
        fi
    else
        aws_info="${aws_info}%f"
    fi

    echo "$aws_info"
}

function current_venv() {
    if [[ -n "$VIRTUAL_ENV" ]]; then
        local dir=$(basename "$VIRTUAL_ENV")
        echo "%F{yellow}($dir)%f"
    fi
}

function user_info() {
    if [[ -n $SSH_CONNECTION ]]; then
        if [[ "$USER" == "root" ]]; then
            echo "%F{red}$USER@%m%f"
        else
            echo "%F{cyan}$USER@%m%f"
        fi
    elif [[ "$USER" == "root" ]]; then
        echo "%F{red}$USER@%m%f"
    else
        echo "%F{blue}$USER@%m%f"
    fi
}

function current_dir() {
    local _max_pwd_length="65"
    if [[ ${#PWD} -gt ${_max_pwd_length} ]]; then
        echo "%B%F{white}%-2~ ... %3~%f%b"
    else
        echo "%B%F{white}%~%f%b"
    fi
}

function git_prompt_info() {
    if ! git_repo_check; then
        return
    fi

    local branch_name="$(git_current_branch)"
    local git_status=""

    # Get git status
    local status_output="$(git status --porcelain 2>/dev/null)"

    # Nerd Font icons using echo -e for proper rendering
    local icon_untracked="󱀶"                       # question file
    local icon_added="$(echo -e '\uf067')"         # plus
    local icon_modified="$(echo -e '\uf459')"      # modified file
    local icon_deleted="$(echo -e '\uf068')"       # minus
    local icon_renamed="$(echo -e '\uf061')"       # arrow
    local icon_unmerged="$(echo -e '\uf071')"      # exclamation
    local icon_clean="$(echo -e '\uf00c')"         # check mark
    local icon_stash="$(echo -e '\uf01c')"         # stash
    local icon_branch="$(echo -e '\ue0a0')"        # git branch

    if [[ -n "$status_output" ]]; then
        # Check for different types of changes
        [[ -n $(echo "$status_output" | grep "^??") ]] && git_status="${git_status}%F{red}${icon_untracked}%f "
        [[ -n $(echo "$status_output" | grep "^A") ]] && git_status="${git_status}%F{green}${icon_added}%f "
        [[ -n $(echo "$status_output" | grep "^M\|^ M") ]] && git_status="${git_status}%F{yellow}${icon_modified}%f "
        [[ -n $(echo "$status_output" | grep "^D\|^ D") ]] && git_status="${git_status}%F{red}${icon_deleted}%f "
        [[ -n $(echo "$status_output" | grep "^R") ]] && git_status="${git_status}%F{magenta}${icon_renamed}%f "
        [[ -n $(echo "$status_output" | grep "^UU") ]] && git_status="${git_status}%F{red}${icon_unmerged}%f "
    else
        # Clean working directory
        git_status="%F{green}${icon_clean}%f "
    fi

    # Check for stashes
    if git stash list 2>/dev/null | grep -q "stash@"; then
        git_status="${git_status}%F{blue}${icon_stash}%f "
    fi

    echo "%F{green}${icon_branch} ${branch_name}%f ${git_status}"
}

function git_remote_status() {
    if ! git_repo_check; then
        return
    fi

    # Check if we have an upstream branch
    local upstream="$(git rev-parse --abbrev-ref @{upstream} 2>/dev/null)"
    if [[ -z "$upstream" ]]; then
        return
    fi

    local ahead_behind="$(git rev-list --count --left-right @{upstream}...HEAD 2>/dev/null)"

    if [[ -n "$ahead_behind" ]]; then
        local behind="$(echo "$ahead_behind" | cut -f1)"
        local ahead="$(echo "$ahead_behind" | cut -f2)"

        local icon_up="$(echo -e '\uf062')"     # up arrow
        local icon_down="$(echo -e '\uf063')"   # down arrow

        local remote_status=""
        [[ "$ahead" != "0" ]] && remote_status="${remote_status}%F{green}${icon_up} ${ahead}%f  "
        [[ "$behind" != "0" ]] && remote_status="${remote_status}%F{red}${icon_down} ${behind}%f"

        echo "$remote_status"
    fi
}

function current_caret() {
    local caret="$(echo -e '\u276f')"  # ❯ symbol
    if [[ "$USER" == "root" ]]; then
        echo "%F{red}# %f"
    else
        echo "%F{green}${caret} %f"
    fi
}

function return_status() {
    local warning="$(echo -e '\u26a0\ufe0f')"  # ⚠️ warning emoji
    echo "%(?..%F{red}%? ${warning} %f)"
}

# ========== Prompt configuration ==========
PROMPT='
$(current_venv) $(user_info):$(current_dir)  $(git_prompt_info) $(aws_prompt_info)
$(current_caret)'
PROMPT2='. '
RPROMPT='%{$(echotc UP 1)%} $(git_remote_status)   $(return_status)   %{$(echotc DO 1)%}'

# ========== Color configuration ==========
# LS Colors - Made with: http://geoff.greer.fm/lscolors/
export LSCOLORS="gxfxcxdxbxegedabagacad"
export LS_COLORS="di=36:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43"
export CLICOLOR=1  # Turn on colors with default unix `ls` command

# GREP Colors
export GREP_COLORS='mt40;93'

# Internal zsh styles: completions, suggestions, etc
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%B--- %d%b"
