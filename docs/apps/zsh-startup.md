---
icon: material/timer-outline
---

# zsh-startup

Times this machine's interactive zsh, so a startup regression is a number rather
than an impression. `zsh-startup --help` carries the three reports, the sampling
method and why each was chosen; this page is the part that is about the repo
rather than about the tool.

## It measures the machine, and there is no threshold

No budget, and no build that fails on a slow number. A startup time is a property
of the machine as much as of the config — a laptop on battery and a desktop
disagree by more than most regressions — so a threshold set here would fail on
the slowest box in the fleet and pass everywhere a regression actually landed.

What is guarded instead is the *mechanism*, in `tests/shell/test_zshrc_startup.py`:
that every autoloaded completion is generated before compinit reads fpath, and
that a generated file compinit would skip is refused rather than written.

## Where the numbers came from

The measurement that motivated the completion split is in
[Profiling Zsh Startup](../learnings/profiling-zsh-startup.md), which is also
where the `ZSHRC_DEBUG` trace and the `PS4` whole-startup trace are written down.
This tool covers the third case those two miss: the wall clock, repeated, with a
median rather than one run.
