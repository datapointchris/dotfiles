# Desktop Memory Reservations

The Wayland workstation runs several agent sessions at once, each starting builds,
tests and data jobs at full parallelism. Together they fill RAM, and the desktop
froze when they did: the terminal stopped echoing, tmux stopped switching, and
music cut in and out. The CPU was not the cause. Each tmux pane is its own cgroup,
so the kernel already splits CPU between panes by weight. Memory had no such split.

`install/system.yml` declares two changes against that. The kernel is told never to
reclaim the desktop's memory, and zram is sized so that whatever does swap stays off
the disk. The investigation behind both, with its measurements, is the hub's
*Desktop Freezes Under Memory Pressure* page under Systems → Linux.

## A freeze is reclaim taking the desktop's pages, not a build taking the CPU

When RAM fills, the kernel reclaims the least recently used pages from every
cgroup. Between keystrokes the terminal, tmux and the audio daemons look idle, so
their pages go to swap first. The next keystroke or audio buffer faults them back.
That read queues behind the swap traffic of the job that filled RAM, so whatever is
touched next stalls. PipeWire's audio thread runs real-time and preempts any
compiler. A page fault still blocks it like any other thread.

## MemoryMin keeps the desktop resident while jobs run unthrottled

`MemoryMin` makes the kernel skip a cgroup during reclaim while its usage is under
the figure. It protects what the cgroup uses and holds nothing back while unused,
so an idle reservation is free memory for everyone else. Each figure sits above the
peak that unit reached under a full load of agent work:

| Unit | Reserves | Why it is reserved |
| --- | --- | --- |
| `pipewire`, `pipewire-pulse`, `wireplumber` | 64M each | Audio, and the PulseAudio bridge browsers play through |
| `app-com.mitchellh.ghostty.service` | 256M | The terminal |
| `app-ghostty-surface-transient-*.scope` | 256M each | Each terminal surface; the tmux server lives in the one that started it |
| `app-com.vivaldi.Vivaldi-*.scope` | 512M | Vivaldi's main process |
| `session-*.scope` | 3072M | Hyprland, waybar, most of Vivaldi's renderers and the music webview |

The last row is large because the login session holds more than the compositor.
Processes Hyprland starts inherit its session scope. Vivaldi's main process runs in
an app scope of its own, but most of its renderers stay in the session scope, and
so does the WebKit webview playing music.

Agent sessions are not reserved. A Claude Code session shares its pane's cgroup
with every build it starts, so protecting the session would protect its builds too.

## A reservation holds only as far as every ancestor's does

A cgroup's effective protection is capped by its ancestors' `memory.min`. When
children claim more than a parent allows, the kernel scales each child's share by
its usage. So every level from `user.slice` down carries the sum of what sits
beneath it, and the comment above the rows in `install/system.yml` is where that
arithmetic is kept. Change a leaf and change its parents with it.

The cgroup2 filesystem here is mounted without `memory_recursiveprot`, which
`rg cgroup2 /proc/self/mountinfo` shows. Without it, a parent's protection reaches
only the children that claim their own, and the agent panes beside ghostty in
`app.slice` claim none. With it, a parent's unclaimed protection would be shared
out to every child. Sizing each parent to the sum of its children keeps that
leftover small should a later boot mount it.

systemd 262 has no `DefaultMemoryMin=`. A slice cannot hand a default to its
children, so pipewire, pipewire-pulse and wireplumber each carry their own row.

Prefix drop-ins reach transient units. `app-ghostty-surface-transient-.scope.d/`
applies to every surface scope ghostty creates, including ones already running at
`daemon-reload`. That is what makes the tmux reservation possible at all, since the
scope's number changes with every surface.

An SSH login is a `session-*.scope` as well, and gets the same 3072M. While one is
running, it shares `user-.slice`'s 5312M with Hyprland's session, so a large job
over SSH thins the desktop's protection for as long as it runs.

## zram sized to RAM keeps a swap-in off the disk

zram-generator defaults to `min(ram / 2, 4096)` MiB. That is 4 GiB here, which one
build fills before the rest of its swap goes to the NVMe swapfile. `zram-size = ram`
lets zram take a full RAM's worth of swapped pages. At the roughly 4:1 ratio zstd
reaches on this swap, a full device costs about a quarter of RAM. A swap-in from
zram costs a decompression rather than a disk read queued behind other writes.

`vm.page-cluster = 0` stops swap readahead. From zram, each page read ahead is a
decompression nobody asked for. It also stops readahead from the disk swapfile,
which stays below zram at priority 10 so `/tmp`, a tmpfs, can still leave RAM.

A running zram device keeps its size until `systemd-zram-setup@zram0.service`
restarts. The restart swaps the device off first, which moves its whole contents
back into RAM or onto the swapfile, so it is best done at a quiet moment or left to
the next boot.

## Ceilings, kills and lower parallelism were each turned down

- **A memory ceiling on agent work** (`MemoryHigh`, `MemoryMax`) would make jobs
  reclaim from themselves at a fixed size. The machine has the memory, and a
  ceiling slows a job that would have finished.
- **Killing under pressure** (systemd-oomd, earlyoom, MGLRU's `min_ttl_ms`) ends
  the freeze by ending a process. oomd kills a whole cgroup, and a pane's cgroup
  holds its agent session, so the session dies with its build. Sessions are never
  to be killed.
- **Lower build parallelism** (cargo's `build.jobs`, Go's `-p`) caps one build and
  slows it. Builds run as fast as the machine allows.
- **`nice` on a build** reorders tasks inside one cgroup only. The kernel splits
  CPU between cgroups by `cpu.weight` first, and each pane is its own cgroup.

## Protected cgroups stop gaining swap when it works

A protected unit's `memory.swap.current` stops growing while agent work swaps, and
its memory and IO pressure stay near zero. Pages swapped out before the
reservation landed come back as they are touched, so the first reading after a
deploy still shows old swap.

```bash
A=/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service
for d in $A/session.slice/pipewire.service $A/app.slice/app-com.mitchellh.ghostty.service; do
  echo "$d: min=$(cat $d/memory.min) swap=$(cat $d/memory.swap.current)"
  awk '/full/' $d/memory.pressure $d/io.pressure
done
```

Run it during a heavy build. A protected unit with swap still growing means its
reservation is below its use, or an ancestor's sum no longer covers its children.
