# shellcheck shell=bash
# shellcheck disable=SC2154
# SC2154 = Variables referenced but not assigned (from sourced files)

# Role overlay for the work machine — loaded when MACHINE_ROLE=work, whatever
# the OS underneath happens to be. Everything here is employer infrastructure
# (CIFS shares, Okta) rather than anything WSL provides, which is why it is not
# in shell/wsl/wsl.sh: a personal WSL box would want none of it.
#
# WORK_USER is the employee ID the shares authenticate as. It reads from ~/.env
# so the value is per-machine rather than checked in; the default preserves the
# existing work box until its ~/.env carries one.
WORK_USER="${WORK_USER:-600002371}"
WORK_DOMAIN="${WORK_DOMAIN:-MEDPRO}"

_mount_work_share() {
  local remote="$1" mountpoint="$2"
  sudo mkdir -p "$mountpoint"
  mountpoint -q "$mountpoint" && sudo umount -f "$mountpoint"
  sudo mount -t cifs "$remote" "$mountpoint" \
    -o "username=${WORK_USER},domain=${WORK_DOMAIN},vers=3.0,uid=$(id -u),gid=$(id -g)"
}

#@mount-h
#--> Mount user network h drive CIFS share at /mnt/h
mount-h() {
  _mount_work_share "//prodfs011/dfs_users/${WORK_USER}" /mnt/h
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
