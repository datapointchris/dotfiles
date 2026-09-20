---
icon: material/lightbulb
---

# Learnings

Each learning is one bug, gotcha, or measured lesson from dotfiles development.

## Search by the symptom, not by the tool

Reach for these before diagnosing a broken install, a tool that stopped working, or an
error that makes no sense. A learning quotes the error text verbatim wherever there is
one, so the string on screen is the string to search for:

```bash
rg -i "no route to host" docs/learnings/
```

The site search above covers the same ground from a browser.

General technical notes that name nothing in this repo live on the hub at
<https://docs.ichrisbirch.com/>, so a symptom search covers both.

## The record, listed by what it looked like

- [App Installation Patterns](app-installation-patterns.md) — a new CLI tool and no obvious place
  for it; the four categories, and what picks between them
- [uv Tool Git Pins and Self-Update](uv-tool-git-pins.md) — the updater reports a tool already at
  the latest version, and the tool itself announces one eight releases newer
- [Minimal Manifest for Servers](minimal-manifest-for-servers.md) — a headless LXC box pointed at
  the only available manifest installs docker, ffmpeg and every desktop package
- [Undeclared Transitive Dependency](undeclared-transitive-dependency.md) — `ModuleNotFoundError:
  No module named 'click'` from the installed tool, after ruff, mypy, pytest and four CI jobs
  passed and the change merged
- [Symlinks Path Gotchas](symlinks-path-gotchas.md) — `.gitconfig` silently stops being symlinked,
  and a second path bug beside it that the unit tests did not catch
- [A Test Writes Through a Deployed Symlink](a-test-writes-through-a-deployed-symlink.md) — every
  tool that resolves the repo registry fails at once, and a deployed config is no longer a symlink
- [WSL Credential Helper Exec Format Error](wsl-credential-helper-exec-format-error.md) —
  `git-credential-manager.exe: Exec format error`, re-authenticating does nothing, and a reboot
  fixes it
- [pre-commit Stash Recovery](pre-commit-stash-recovery.md) — a killed pre-commit run and the tree
  comes back without the unstaged changes
- [Shared Stash Across Worktrees](shared-stash-across-worktrees.md) — edits disappear from one
  worktree and surface in another, and `git stash pop` conflicts on files the branch never touched
- [Task Shell Printf Compatibility](task-shell-printf-compatibility.md) — `invalid format char: *`
  from a `printf` that runs fine in a bash script
- [Profiling Zsh Startup](profiling-zsh-startup.md) — new shells intermittently take six seconds
  while most of them open in under half of one
- [Resilient Installation Patterns](resilient-installation-patterns.md) — one unresolvable name
  aborts a whole `brew install` batch, and the loss surfaces phases later as a missing binary
- [cargo binstall Needs Release Binaries](cargo-binstall-needs-release-binaries.md) — an install
  pauses for minutes with no output, which cannot be told from a deadlock
- [A packages.yml Entry Is Not an Install](packages-yml-entry-is-not-an-install.md) — `fnm not
  found` on the offline box, with a complete `packages.yml` entry sitting right there
- [A CIFS Mount Hides a Missing Helper](cifs-mount-hides-a-missing-helper.md) —
  `mount error(113): No route to host` on a fresh distro, with DNS, hosts and routing all correct
- [Pyright Config File Precedence](pyright-config-file-precedence.md) — a basedpyright warning
  survives every LSP setting that should suppress it, including `ignore = { '*' }`
- [Ghostty Shader Reload](ghostty-shader-reload.md) — an edited GLSL shader keeps rendering the old
  picture after a config reload, so every round of tuning looks identical
- [The ORA by Kanto Volume Drop-in](usb-dac-lies-about-its-volume-range.md) — the lower half of the
  volume slider is silent on a USB DAC, and waybar's percentage means nothing
- [Finding Where a Slow Run Went](finding-where-a-slow-run-went.md) — `dotfiles check` and `apply`
  take five silent minutes, and nothing in the output or the run record says which part was slow
- [A Conflicting Package Blocks an Install Forever](a-conflicting-package-blocks-an-install-forever.md)
  — `yay -S exited 1` on every run after a four-minute source build, with the reason only in the
  transcript
- [Go Was on No PATH, and Nothing Said So](go-was-on-no-path-and-nothing-said-so.md) — Go tools
  report an `unknown` version so `apply` never upgrades them, and gopls cannot find `go`
- [A Unix Socket Path Is Shorter Than tmp_path](unix-socket-path-is-shorter-than-tmp-path.md) —
  `tmux.sock (File name too long)` at fixture setup, on macOS only
- [A Cache Outlives the File You Restored](a-cache-outlives-the-file-you-restored.md) — a test
  fails on a mutation the file no longer contains, and two identical mypy runs disagree by hundreds
  of errors
