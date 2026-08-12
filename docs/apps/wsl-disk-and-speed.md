# WSL disk and speed

Two apps, deployed only where `host: wsl`. `wsl-reclaim` is about the disk that
never shrinks; `wsl-doctor` is about everything else that makes WSL feel slow.
Neither exists on Arch or macOS, because neither question does.

## Deleting files inside WSL never shrinks the disk

Every distro's filesystem is one file on the Windows side, `ext4.vhdx`. It grows
to accommodate what the guest writes and it never contracts on its own. A Docker
cache that peaked at 40GB in March is still charging Windows 40GB in August,
long after `docker system prune` reported the space free. `df` inside the distro
and the file size on the host answer different questions, and only the second
one is what the C: drive is short of.

Reclaiming space is therefore two separate acts, and doing only one of them
accomplishes nothing:

1. Free the blocks inside the guest — `wsl-reclaim clean`
2. Compact the file on the host — `wsl-reclaim compact`

The compaction is the part that has to happen on Windows, with administrator
rights, while WSL is shut down. `compact` writes a PowerShell script into the
Windows temp directory and launches it elevated and **detached**. Detached
because the script's second instruction is `wsl --shutdown`, which kills every
process in the distro — including, if it were a child, the thing doing the
compacting. That would leave the vhdx attached read-only, which is a worse state
than the one being fixed.

Where the file lives is read out of the registry rather than assumed.
Distributions installed before WSL 2.4 sit under
`%LOCALAPPDATA%\Packages\<PackageFamilyName>\LocalState` and newer ones under
`%LOCALAPPDATA%\wsl\{guid}`, so a hardcoded path is wrong on about half the
machines that have one.

## Sparse mode is deliberately not offered

`sparseVhd=true`, or `wsl --manage <distro> --set-sparse true`, makes the vhdx
release blocks continuously. It is the obvious fix and it reads like exactly
what a disk that never shrinks needs.

It has been gated behind `--allow-unsafe` since WSL 2.5.6, after reports of ext4
corruption. Worse for the purpose here, a sparse vhdx cannot be compacted by any
other means — diskpart refuses with *"Virtual hard disk files must be
uncompressed and unencrypted and must not be sparse"* — and turning it back off
re-materialises every hole, costing a full compact cycle to undo. So the escape
hatch from the risky option is the option it replaced.

`tests/shell/test_wsl_tools.py` pins the refusal rather than trusting the
comment that explains it.

`Optimize-VHD` is not offered either. It needs the Hyper-V PowerShell module,
absent on Windows Home and on any managed machine that never enabled the
feature. diskpart does the same job everywhere.

## Why WSL feels slow, and what `wsl-doctor` measures

The causes are few and specific, and none of them announce themselves. Each
check ends in a named change rather than a number, because a number the reader
cannot act on is the failure mode this tool exists to avoid.

**The Windows PATH is on your PATH.** `appendWindowsPath` defaults to true, so
every Windows PATH entry is appended to the guest's. A command that *exists* is
found and cached; a command that does **not** stats every directory in turn, and
each `/mnt` entry is a 9p round trip. Every typo pays it, and so does every
`command -v` guard in every shell library and prompt — which is why the shell
feels slow rather than any one program. `wsl-doctor` counts the entries and
times a miss.

Turning it off is a genuine tradeoff and the tool reports it rather than making
it. `win32yank.exe` is how this repo's WSL clipboard works, and `explorer.exe`,
`code` and `powershell.exe` all stop resolving. The fix is to set
`appendWindowsPath=false` under `[interop]` in `/etc/wsl.conf` *and* symlink the
handful of `.exe` files actually used into `~/.local/bin`.

**Files on `/mnt/c`.** drvfs crosses a protocol boundary per operation, so
anything that walks a tree — `git status` above all — is an order of magnitude
slower than the same repo under `~`. `wsl-doctor bench` writes 64MB to each
filesystem so the gap is a measured number rather than folklore.

**The page cache being dropped.** `autoMemoryReclaim` defaults to `dropCache`,
which returns memory to Windows by discarding the guest's page cache outright.
The next build then re-reads from disk every file the last one just read.
`gradual` reclaims idle memory without that cliff, and idle memory was the part
worth reclaiming.

**Defender scanning the vhdx.** Every read and write inside the guest is scanned
on the host unless the disk is excluded. `wsl-doctor` reports whether it is;
adding the exclusion needs an administrator and is often blocked by policy on a
managed machine, so the tool names it and stops.

## `.wslconfig` is installed, not symlinked

`.wslconfig` configures the VM that hosts every distro, so it lives in
`%UserProfile%` on the Windows side. The symlink manager deploys below `$HOME`,
and `$HOME` here is inside the guest, so this one is copied by
`install/wsl/install-wslconfig.sh` — `task wsl:tune` — with a `--check` mode
that reports drift the way `sync-windows-shell.sh` does.

An existing file is backed up rather than replaced silently. It is a file
somebody edits by hand at the exact moment something is broken, and losing that
edit to an unrelated install would say nothing.

The template carries only settings that are an actual decision. Anything WSL
already defaults to correctly is left out rather than restated, so a line in
that file always means *we chose differently, and here is why*.

Changes need `wsl.exe --shutdown` and about eight seconds. WSL keeps the VM
alive briefly after the last shell exits, and relaunching immediately reads the
old configuration while appearing to have applied the new one.
