# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

# Role overlay for the work machine — loaded when MACHINE_ROLE=work, whatever
# the OS underneath happens to be. Everything here is employer infrastructure
# (CIFS shares, Okta) rather than anything WSL provides, which is why it is not
# in shell/wsl/wsl.sh: a personal WSL box would want none of it.
#
# The share account defaults to the Windows profile name: the machine is
# domain-joined, so /mnt/c/Users/<name> and the CIFS username are one identity.
# WORK_USER exists only for a machine where they genuinely differ, which is why
# it is not in flags.yml's required list and WINDOWS_USER is.
#
# Values come from ~/.env below the OVERRIDES marker, never from this repo: an
# employee ID and an employer domain do not belong in it, and a wrong default
# would mount a share as the wrong user rather than failing.
#
# Checked here rather than at file scope: a `${VAR:?}` while sourcing aborts the
# rest of this file, so an unset value would cost every function below it on
# every new shell instead of failing the one command that needs it.
# One definition of the share account, for both the credential and the path of
# the personal home share.
_work_user() { printf '%s' "${WORK_USER:-${WINDOWS_USER:-}}"; }

_mount_work_share() {
  local remote="$1" mountpoint="$2"
  local user
  user="$(_work_user)"

  if [[ -z "$user" || -z "${WORK_DOMAIN:-}" ]]; then
    echo "Set WINDOWS_USER and WORK_DOMAIN in ~/.env (below the OVERRIDES marker)" >&2
    return 1
  fi

  sudo mkdir -p "$mountpoint"
  mountpoint -q "$mountpoint" && sudo umount -f "$mountpoint"
  sudo mount -t cifs "$remote" "$mountpoint" \
    -o "username=${user},domain=${WORK_DOMAIN},vers=3.0,uid=$(id -u),gid=$(id -g)"
}

#@mount-h
#--> Mount user network h drive CIFS share at /mnt/h
mount-h() {
  _mount_work_share "//prodfs011/dfs_users/$(_work_user)" /mnt/h
}

#@mount-appserver
#--> Mount work appserver CIFS share at /mnt/devdsapp001
mount-appserver() {
  _mount_work_share '//devdsapp001/E$' /mnt/devdsapp001
}

#@mount-dfsapp
#--> Mount DFS app CIFS share at /mnt/dfs_app/Data_Science
mount-dfsapp() {
  _mount_work_share //prodfs011/Data_Science /mnt/dfs_app/Data_Science
}

#@aws-login
#--> Login to AWS via Okta for dev or prod environment
aws-login() {
  local environment="${1:-dev}"
  local profile
  local win_home

  # Use $HOME on Git Bash, $winchris on WSL
  if [[ -n "$MSYSTEM" ]]; then
    win_home="$HOME"
  else
    win_home="$winchris"
  fi
  local okta_script="$win_home/.local/bin/okta-awscli.exe"

  case $environment in
    dev)
      profile=AWS-DataScienceLower-Dev-DataScientist
      ;;
    prod)
      profile=AWS-DataScienceProd-ReadOnly
      ;;
    *)
      echo "Unknown environment, use 'dev' or 'prod'"
      return
      ;;
  esac

  "$okta_script" --profile "$profile" --okta-profile "$profile" --force --verbose
  export AWS_PROFILE=$profile
  date
}

alias slack='uv run --no-project --with=keyboard python ~/code/buzz.py'
