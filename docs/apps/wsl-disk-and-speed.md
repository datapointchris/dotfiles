# WSL disk and speed

One app, `wsl-tools`, deployed only where `host: wsl`. It does not exist on Arch
or macOS, because the questions it answers do not.

## One binary, because this gets reached for a few times a year

It began as `wsl-tools` and `wsl-tools doctor` side by side, which reads better at
the point of use — `wsl-tools compact` beats `wsl-tools compact`. That is the
wrong thing to optimise at this frequency. The cost of a rarely-used tool is not
typing the verb; it is remembering that the tool exists and what it was called,
and then having to go and find what the *other* ones were named. One name that
lists its own verbs is findable. A family is something you go looking for.

So a bare `wsl-tools` prints the verb list rather than doing any work, and the
verbs are flat — `status`, `doctor`, `clean`, `compact`, `rebuild`, `bench` —
because two levels of subcommand is where this would get unwieldy.

It is one *file* as well as one binary. The shell overlay at
`~/.local/shell/host/wsl` is sourced by every interactive shell, so splitting
the implementation into a library there would put `clean` and `report` into the
shell's namespace and pay to parse them at every prompt.

## Deleting files inside WSL never shrinks the disk

Every distro's filesystem is one file on the Windows side, `ext4.vhdx`. It grows
to accommodate what the guest writes and it never contracts on its own. A Docker
cache that peaked at 40GB in March is still charging Windows 40GB in August,
long after `docker system prune` reported the space free. `df` inside the distro
and the file size on the host answer different questions, and only the second
one is what the C: drive is short of.

Reclaiming space is therefore two separate acts, and doing only one of them
accomplishes nothing:

1. Free the blocks inside the guest — `wsl-tools clean`
2. Shrink the file on the host — `wsl-tools compact` or `wsl-tools rebuild`

The second step has two routes and which one is available is not a preference.
`wsl-tools status` probes the account and says which.

The compaction is the part that has to happen on Windows, with administrator
rights, while WSL is shut down. `wsl-tools compact` writes a PowerShell script into the
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

## Without a Windows administrator, the only route is to rebuild the disk

diskpart requires elevation, and so does `Optimize-VHD` and so does adding a
Defender exclusion. On a managed machine where UAC asks for somebody else's
password, all three are closed and nothing shrinks the file in place.

`wsl-tools rebuild` is the way through. It does not compact the disk; it
throws it away and writes a new one from a tar of the filesystem, so the result
is the size of the data rather than of the high-water mark the old disk once
reached. `wsl --export`, `wsl --unregister` and `wsl --import` are all
user-scope operations.

The window between unregister and import is the whole risk, and three things
narrow it. Free space is checked before anything is shut down, so the common
failure never starts. The archive is read back with `tar -tf` before the distro
is destroyed, because an export that exits 0 and leaves an unreadable file is
the failure that matters. The archive is kept afterwards and the re-import
command is printed *before* the step that might need it.

One thing the rebuild does that a compaction does not: it writes `[user]
default=` into `/etc/wsl.conf` first. The default user is a property of the
Store launcher's registration and an imported distro has no launcher, so
without it the rebuilt distro starts as root — which reads as a broken rebuild
rather than a missing setting.

## Rebuilding the disk, versus rebuilding the machine

There is a third option that is not in this tool: back up with safekeep, delete
the distro, install a fresh one, run `dotfiles apply`, restore, and carry on.
It reclaims the same space and needs no administrator either.

The two are not competing, because they answer different questions.
`wsl-tools rebuild` preserves the filesystem exactly and takes about as long
as copying the data twice. Deleting and reinstalling preserves only what
safekeep covers, takes as long as a full machine setup — and **proves the
machine is reproducible**, which is the entire premise of this repo and of
safekeep. It also drops the accumulated drift that a byte-exact rebuild
faithfully carries across.

So: `rebuild` for the routine reclaim, where the disk is the only problem.
Delete and reinstall when it is worth finding out — deliberately, with time in
hand — whether the rebuild path still works. A reproducibility claim that is
never exercised is a claim, and the moment it is discovered to be false is
otherwise an emergency rather than an afternoon.

The one asymmetry worth naming: safekeep writes to the network drive, while
`rebuild` writes its archive to a local disk it has to fit on. When the disk
being reclaimed is the full one, the backup that leaves the machine is the
safer of the two.

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

## Why WSL feels slow, and what `wsl-tools doctor` measures

The causes are few and specific, and none of them announce themselves. Each
check ends in a named change rather than a number, because a number the reader
cannot act on is the failure mode this tool exists to avoid.

**The Windows PATH is on your PATH.** `appendWindowsPath` defaults to true, so
every Windows PATH entry is appended to the guest's. A command that *exists* is
found and cached; a command that does **not** stats every directory in turn, and
each `/mnt` entry is a 9p round trip. Every typo pays it, and so does every
`command -v` guard in every shell library and prompt — which is why the shell
feels slow rather than any one program. `wsl-tools doctor` counts the entries and
times a miss.

Turning it off is a genuine tradeoff and the tool reports it rather than making
it. `win32yank.exe` is how this repo's WSL clipboard works, and `explorer.exe`,
`code` and `powershell.exe` all stop resolving. The fix is to set
`appendWindowsPath=false` under `[interop]` in `/etc/wsl.conf` *and* symlink the
handful of `.exe` files actually used into `~/.local/bin`.

**Files on `/mnt/c`.** drvfs crosses a protocol boundary per operation, so
anything that walks a tree — `git status` above all — is an order of magnitude
slower than the same repo under `~`. `wsl-tools bench` writes 64MB to each
filesystem so the gap is a measured number rather than folklore.

**The page cache being dropped.** `autoMemoryReclaim` defaults to `dropCache`,
which returns memory to Windows by discarding the guest's page cache outright.
The next build then re-reads from disk every file the last one just read.
`gradual` reclaims idle memory without that cliff, and idle memory was the part
worth reclaiming.

**Defender scanning the vhdx.** Every read and write inside the guest is scanned
on the host unless the disk is excluded. Adding an exclusion needs an
administrator, so `wsl-tools doctor` words the finding by what the account can
actually do — an action where it can be taken, context where it cannot. A fix
nobody on this machine can apply is noise in a list of things to change.

`wsl-tools doctor` also reports where the distro is installed. Anything outside
`Packages\<PackageFamilyName>` arrived through `wsl --import`, which means the
disk has been rebuilt before — the machine remembers the procedure even when
nobody does.

## Three verbs for looking closer, when `doctor` is not enough

`doctor` answers "what should I change". These answer "what is actually going
on", which is the question you have when the answer is not on the list.

**`processes`** shows what holds memory and CPU inside the VM, then what Windows
is charged for the whole thing. The gap between those two numbers is the point.
Linux reports page cache as free, Windows charges for it as resident, and that
difference is why WSL looks like it leaks memory when it does not. It is also
exactly what `autoMemoryReclaim` governs, so the number tells you whether that
setting is worth touching on this machine.

**`mounts`** says which paths are native ext4 and which cross to Windows. The
filesystem name for the crossing is not stable — `drvfs` on older builds,
`virtiofs` on newer, `9p` as what mount reports for both in some versions — so
all three are classified. Missing one would report the interop mount as native
on exactly the machines that have it. Docker's overlay layers collapse to a
count: there is one mount per image, and unsummarised they are the entire output
on any box that runs containers.

**`startup`** times shell startup, then times it again with the interop PATH
entries removed. The delta is what turning `appendWindowsPath` off would buy,
per new shell. That change has a real cost — `win32yank.exe` is how the
clipboard works here, and `explorer.exe` and `code` stop resolving — so it is
worth knowing the size of the prize before paying it. Without this you can only
evaluate the change by living with it for a week.

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
