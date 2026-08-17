# uv Tool Git Pins and Self-Update

## Problem

The fleet updater reported `syncer already at latest (4.3.0)` while syncer itself, run a
minute later, announced v5.3.0 — eight releases newer. The updater was not lying about
what it observed. It ran `uv tool upgrade syncer`, which exits 0 having changed nothing,
so the before/after version comparison correctly found no movement.

The cause is in uv's receipt (`~/.local/share/uv/tools/<tool>/uv-receipt.toml`), which
records the requirement a tool was installed from:

```toml
requirements = [{ name = "syncer", git = "https://github.com/datapointchris/syncer.git?rev=v6.0.0" }]
```

`uv tool upgrade` re-resolves the requirement it finds. A pinned tag resolves to the same
commit every time, so upgrade is a permanent no-op for that tool — and it stays silent
about being one.

The pin was written by the tool itself. `pyselfupdate` reinstalls as `<tool> @
git+<url>@<tag>`, so the first `syncer update` rewrote a receipt that dotfiles had
installed unpinned, and removed the tool from the fleet updater's reach for good.

## Solution

Pin deliberately, in both directions, rather than fighting over the receipt.
`git_uv_tools` install as `<name> @ git+<repo>@<newest release tag>`. The reasoning is
the module docstring in `src/dotfiles/providers/uvtool.py`. Moving a pin means
reinstalling the requirement; `uv tool upgrade` cannot do it.

`tracks_branch: true` in packages.yml marks the exception — a repo publishing no releases
has no tag to pin, so it follows its default branch and is upgraded with `uv tool
upgrade`.

Measuring the pin is the other half of the problem. A checker that asks only whether a
tool's directory exists reports every `git_uv_tools` entry converged forever — four tools
sat months behind while `plan` said there was nothing to do, which is the receipt's
blindness reproduced in the checker. So these entries are compared against the releases
cache like every other section that installs from a named repo, and the *installed* side
is read back from the receipt rather than by running the tool. `uv tool install` does none
of the version stamping a release build does, so a tool that answers `--version` answers
with whatever its source hardcodes, and several of them cannot answer at all.

## Key Learnings

- **Pinning to releases means unreleased commits on `main` are deliberately not
  installed.** Cutting a release is what ships work to the fleet. The migration moved
  three tools back from `main` HEAD to their release tag; all the skipped commits were
  `ci:`/`docs:`/`style:`.
- **Two updaters writing the same receipt must agree on its shape.** Whichever ran last
  won, and the loser reported success either way.
