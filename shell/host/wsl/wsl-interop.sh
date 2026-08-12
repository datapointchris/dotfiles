# shellcheck shell=bash

# Talking to the Windows side from inside the guest. Sourced by the wsl-* apps
# and, harmlessly, by an interactive shell — these are function definitions and
# nothing here runs at source time.
#
# Extracted when the third caller appeared. Two copies of a PowerShell escaping
# rule is a duplication; three is a place for them to disagree, and the one that
# matters most is the elevation probe, whose wrong answer sends a user at a UAC
# prompt they cannot satisfy.

# Windows console tools emit UTF-16LE, which reaches bash as ASCII interleaved
# with NULs and compares equal to nothing. Stripping NUL and CR is what makes the
# output usable.
#
# </dev/null because PowerShell inherits stdin and will consume a caller's loop
# input — see docs/learnings/wsl-powershell-stdin-consumption.md.
powershell_out() {
  powershell.exe -NoProfile -NonInteractive -Command "$1" </dev/null 2>/dev/null | tr -d '\r\0'
}

windows_userprofile() {
  local profile
  profile=$(powershell_out "Write-Output \$env:USERPROFILE" | tr -d '\n')
  [[ -n "$profile" ]] || return 1
  wslpath -u "$profile" 2>/dev/null
}

windows_temp_dir() {
  local temp
  temp=$(powershell_out "Write-Output \$env:TEMP" | tr -d '\n')
  [[ -n "$temp" ]] || return 1
  wslpath -u "$temp" 2>/dev/null
}

# Whether this Windows account can elevate at all — not whether it is elevated
# now, which unelevated is always no and answers nothing.
#
# Group membership rather than IsInRole(Administrator). Under UAC an admin
# account runs on a filtered token where IsInRole answers false, so a probe built
# on it reports every machine as unable to elevate. The Administrators SID is
# still listed on the filtered token, which is the question actually being asked:
# will UAC prompt this user for consent, or for somebody else's password.
windows_can_elevate() {
  local answer
  answer=$(powershell_out "
    \$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    \$administrators = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
    if (\$identity.Groups -contains \$administrators) { Write-Output 'yes' } else { Write-Output 'no' }
  " | tr -d '\n ')

  [[ "$answer" == "yes" ]]
}

# The registry is the only reliable answer. Distros installed before WSL 2.4 sit
# under %LOCALAPPDATA%\Packages\<PackageFamilyName>\LocalState and newer ones
# under %LOCALAPPDATA%\wsl\{guid}, so a hardcoded path is wrong on about half the
# machines that have one.
wsl_base_path() {
  local distro="${WSL_DISTRO_NAME:-}" query base backslash device_prefix
  [[ -n "$distro" ]] || return 1

  # PowerShell string literals are single-quoted so the whole query survives one
  # round of bash double-quoting. \$_ is the pipeline variable and must reach
  # PowerShell unexpanded.
  query="(Get-ChildItem HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Lxss"
  query+=" | Where-Object { \$_.GetValue('DistributionName') -eq '$distro' }).GetValue('BasePath')"

  base=$(powershell_out "$query" | tr -d '\n')
  [[ -n "$base" ]] || return 1

  # BasePath comes back as an extended-length path. wslpath does not understand
  # the \\?\ device prefix and returns nothing at all for one. Assembled from a
  # variable because a literal backslash before a closing quote is unreadable
  # and reads to shellcheck as a botched escape.
  backslash=$'\\'
  device_prefix="${backslash}${backslash}?${backslash}"
  printf '%s\n' "${base#"$device_prefix"}"
}

vhdx_windows_path() {
  local base backslash
  base=$(wsl_base_path) || return 1
  backslash=$'\\'
  printf '%s%sext4.vhdx\n' "$base" "$backslash"
}

vhdx_linux_path() {
  local windows_path
  windows_path=$(vhdx_windows_path) || return 1
  wslpath -u "$windows_path" 2>/dev/null
}
