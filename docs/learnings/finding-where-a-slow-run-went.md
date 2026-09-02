# Finding Where a Slow Run Went

## Problem

`dotfiles check` and `dotfiles apply` took at least five minutes on the WSL work
box. Neither printed anything while they did it: `apply` wrote its rule, then sat
silent through the whole measurement, and `check` printed seven converged rows at
the end as though nothing had taken any time at all.

Nothing in the output, the run record or the verdict said which part was slow.
The engine had clocked every resource since it was written and no renderer showed
the number, so the record held the answer to a question no screen ever asked.

The measurement is where the time goes, and three things dominate it — none
visible from a verdict row:

- **The PATH index.** `evidence.executables_on_path` resolved every name a PATH
  can reach to answer about the hundred a machine declares — 3400 entries on
  Arch, at three syscalls each. On WSL with `appendWindowsPath` left on, `$PATH`
  carries `/mnt/c/Windows/System32` and its neighbors, every one of those
  syscalls crosses drvfs, and the count is in the tens of thousands.
- **Version probes.** One `<binary> --version` per installed tool with an
  upstream, strictly one after another. 69 process starts in series.
- **A networked refresh.** Every verb resolves with `refresh=True`, so `plan`,
  `check` and `apply` each ask GitHub for the newest release of every present
  tool. Behind a firewall that answers slowly, this is minutes and it looks
  identical to a hang. `--cached` answers locally instead, and `--package` or
  `--source` cut the refresh to the entries named.
- **The same flag pays for two other things nobody looks for.** `refresh` is a
  session-wide permission to spend the network, not a release-lookup switch.
  `plugins` fetches every clone under it and `evidence.query` asks the managers in
  `syspkg.NETWORKED`. Three of those wear the spelling of a local index read and
  are not one: `yay -Qu --aur` is a second of AUR round trip, `checkupdates` syncs
  a private copy of the pacman database before reading it, and apt's read
  refreshes a copy of `/var/lib/apt/lists` the same way. Measured on Arch: of the
  7.6s a refresh added to a plan, the release lookup was 4.3s and the plugin
  fetches were 2.9s. Measured in the Ubuntu test image: apt's read is 1.8s, of
  which the refresh is 0.9s.

## Solution

Read the run, then read the commands.

```bash
dotfiles check                  # a row per resource, with what measuring it cost
dotfiles report latest          # the same, plus the run's slowest commands
```

A slow resource is colored on its verdict row. A slow command reports itself while
the run is still going:

```text
slow command  command=dpkg-query -W -f=${Package}\n  seconds=291.4
```

`dotfiles logs` is the noun that owns the full stream, one line per command with its
duration, written for every run. The jq recipe that sorts it is in the docstring of
`src/dotfiles/commands/report.py`.

## Key Learnings

- **A duration nobody renders is a duration nobody has.** Per-resource timings
  were recorded correctly for months and answered nothing, because reaching them
  meant already suspecting they were the answer.
- **Announce before the work, not after.** Every event a resource produced
  arrived once it had an answer, so a reader learned its name at the moment the
  wait ended. `Started` carries no finding for exactly this reason.
- **`list()` around a generator throws the streaming away.** The announcements
  existed before the walk was consumed event by event, and all of them still
  arrived at the end, together.
- **Bound a scan by what will be asked of it.** The PATH walk was correct and
  paid for 3400 answers to serve 96 questions. Narrowing it changed no result.
- **Serial subprocesses are the cost on WSL, not the work inside them.** A probe
  is a read that shares nothing, so overlapping eight of them turned the sum of
  every process start into the slowest single one.
- **One serial loop found is not the last one.** Two more turned up later against
  the same argument: the plugin fetches, 2.9s to 0.5s, and a `gh auth token`
  spawned once per request rather than once per run. Both had been there the whole
  time and neither showed on a verdict row, because the resource they belonged to
  was fast enough not to be colored.
- **Suspect the platform's process cost before the code.** Every one of these was
  invisible on Arch and severe on WSL, and none of it is a difference the code
  can see.
