# /tmp Has a Per-User Quota Below Its Size

## Problem

A `go build` fails while `df -h /tmp` shows gigabytes free:

```text
write /tmp/go-build890438877/b968/importcfg: disk quota exceeded
```

`disk quota exceeded` is `EDQUOT`, not the `no space left on device` of a full filesystem.
Arch's `/tmp` is a tmpfs of half the RAM, which systemd's `tmp.mount` mounts with `usrquota`.
At login, `systemd-user-runtime-dir` sets each user's block limit on `/tmp` and `/dev/shm` from
the user record's `tmpLimit`. A record that sets none gets 80% of the mount. The journal shows it
at boot:

```text
systemd-user-runtime-dir[870]: Successfully configured disk quota for UID 1000 on /tmp to 12.2G
```

So one user is refused at 80% of the mount while `df` still reports the rest free. The mount
options show `usrquota` and no limit, because the limit is set per user after the mount.

## Solution

Read the limit and the use from the kernel. quota-tools reaches a tmpfs only through
`quotactl_fd(2)`, so a short ctypes call does it without the package:

```python
import ctypes, os
class Dqblk(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ('bhard', 'bsoft', 'used', 'ihard', 'isoft', 'inodes', 'btime', 'itime')] + [('valid', ctypes.c_uint32)]
q = Dqblk()
fd = os.open('/tmp', os.O_RDONLY | os.O_DIRECTORY)
ctypes.CDLL(None).syscall(443, fd, (0x800007 << 8) | 0, os.getuid(), ctypes.byref(q))  # quotactl_fd, Q_GETQUOTA, USRQUOTA
print(f'limit {q.bhard / 2**20:.1f} GiB, used {q.used / 2**30:.1f} GiB')
```

Then free what the user holds under `/tmp`, or move the writer off it. Syscall 443 is x86_64's
number.

## Key Learnings

- `df` measures the filesystem and the quota measures one user. Free space in `df` says nothing
  about the quota.
- `GOTMPDIR` moves `go build`'s work directory and `t.TempDir()` alike, because `testing` reads it
  too. A test suite that fsyncs SQLite ran in 15 s on the tmpfs and 104 s on ext4, so pointing
  `GOTMPDIR` at disk trades RAM for test time.
- A build killed mid-run leaves its `go-build*` directory behind. tmpfiles ages `/tmp` at ten
  days, and a reboot empties it.
