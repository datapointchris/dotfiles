# Git credential helper fails with `Exec format error` on WSL

## Problem

Git operations against a remote needing the Windows credential manager start failing on the
WSL box. The push or fetch reports an authentication failure, and running the helper by hand
gives:

```text
/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe: Exec format error
```

Nothing about the message points at the real cause. Git reports it as a credential problem,
the credential prompt comes back, and the obvious reading is that the token expired or the
SSO session lapsed. Re-authenticating does not help. A reboot does, which is what makes it
look like a flaky credential store rather than a broken machine.

The helper is reached this way because SSO is the login path, and the Windows
credential manager is what holds that credential. Nothing on the Linux side can supply it.

## Solution

`Exec format error` is `ENOEXEC` from `execve`. Linux cannot run a Windows PE binary on its
own — WSL registers a `binfmt_misc` handler that routes `.exe` files through `/init`, and
when that registration is gone or disabled, **every** `.exe` fails this way, not just the
credential helper.

Confirm it is the interpreter rather than the helper:

```bash
/mnt/c/Windows/System32/cmd.exe /c echo ok    # fails the same way if it is binfmt
cat /proc/sys/fs/binfmt_misc/WSLInterop       # 'enabled' on line 1
cat /proc/sys/fs/binfmt_misc/WSLInterop-late  # the name used on systemd distros
ls /proc/sys/fs/binfmt_misc/                  # entry absent entirely = unregistered
```

Re-enable without rebooting when the entry exists but is disabled:

```bash
sudo sh -c 'echo 1 > /proc/sys/fs/binfmt_misc/WSLInterop'
```

When the entry is gone, `wsl.exe --shutdown` from a Windows terminal re-registers it in
about eight seconds. That is the cheap version of the reboot.

`dotfiles credentials check` reports this directly, and tells it apart from the two faults
it resembles — a helper whose path is wrong, and a helper that runs but has no credential.
`dotfiles credentials show` adds the file each helper was configured in, which matters
because the include chain assembles the configuration from five files. `--probe` asks each
helper for a real credential and is deliberately not part of `check`.

## Key Learnings

- **`Exec format error` from a `.exe` is never about that program.** It is the binfmt
  handler, so test `cmd.exe` before investigating the helper at all.
- **Git blames the credential when the interpreter is what failed.** The helper exits
  non-zero, git sees no credential, and the message it prints describes authentication.
- **A reboot fixing something is evidence, not a fix.** It re-registers binfmt, which
  narrows the cause rather than resolving it.
- **`systemd-binfmt.service` re-applies its own registrations** on a systemd-enabled WSL
  distro and can clear the WSL handler when it runs. Check
  `journalctl -u systemd-binfmt -b` when the failure is intermittent.
- **The helper belongs in `~/.config/git/local.gitconfig`** on that machine, which is
  declared in `install/flags.yml` and restored by safekeep. In `~/.gitconfig` it masks the
  whole include chain, and in the entry point `~/.config/git/config` nothing backs it up.
