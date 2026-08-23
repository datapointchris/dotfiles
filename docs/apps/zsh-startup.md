---
icon: material/timer-outline
---

# zsh-startup

Times this machine's interactive zsh, so a startup regression is a number rather
than an impression. `zsh-startup --help` lists the three modes.

## The wall clock and the trace answer different questions

`ZSHRC_DEBUG=1` has printed a per-step trace since the stall documented in
[Profiling Zsh Startup](../learnings/profiling-zsh-startup.md), and it starts at
the first line of `.zshrc` and stops at the last. Everything zsh does around that
file — the binary, `/etc/zsh/zshenv`, compinit writing its dump, the first prompt
— falls outside it. The number you actually wait for is the wall clock around
`zsh -i`, which is what the default mode reports and what the trace cannot see.

The two disagree by more than the gap suggests, because the trace's own `printf`
per step is inside the measurement.

## Why the median rather than the mean

Startup is a floor plus whatever else the machine was doing, so the distribution
has a long right tail. One descheduled run moves a mean further than a real
regression does. The min is the floor the code could reach on an idle box, and
the spread between min and max says how much of what you saw was the machine.

One warmup run is discarded. The first start of a session pays for page cache on
every plugin file, and that cost is real exactly once — counting it makes the
first measurement of the day look like a regression.

## `--flags` measures this machine, not someone else's

Each row turns one flag off and re-measures, so what it reports is that feature's
cost here. The rows deliberately do not sum: two plugins can each cost 10ms while
turning both off saves 15, because they share work that happens once either way.

The flag names come out of `~/.env`, which is what the shell itself reads, so
nothing about this knows which manifest rendered it. `~/.env` writes every value
as `${NAME:-default}`, so the measurement overrides a flag for one shell and the
file is never touched.

## What it deliberately does not do

No budget, and no threshold that fails. A startup time is a property of the
machine as much as of the config — a laptop on battery and a desktop disagree by
more than most regressions — so a number that fails a build here would fail on
the slowest box and pass everywhere the regression actually landed. What is
guarded instead is the *mechanism*, in `tests/shell/test_zshrc_startup.py`: that
generated completions are written to fpath rather than sourced, and that the
directory joins fpath before compinit reads it.
