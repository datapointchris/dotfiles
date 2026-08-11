# uv Tool Git Pins and Self-Update

## Problem

`task update -- --mine` reported `syncer already at latest (4.3.0)` while syncer itself, run a
minute later, announced v5.3.0 — eight releases newer. The update phase was not lying about what it
observed. It ran `uv tool upgrade syncer`, which exits 0 having changed nothing, so the before/after
version comparison correctly found no movement.

The cause is in uv's receipt (`~/.local/share/uv/tools/<tool>/uv-receipt.toml`), which records the
requirement a tool was installed from:

```toml
requirements = [{ name = "syncer", git = "https://github.com/datapointchris/syncer.git?rev=v6.0.0" }]
```

`uv tool upgrade` re-resolves the requirement it finds. A pinned tag resolves to the same commit
every time, so upgrade is a permanent no-op for that tool — and it stays silent about being one.

The pin was written by the tool itself. `pyselfupdate` reinstalls as `<tool> @ git+<url>@<tag>`, so
the first `syncer update` rewrote a receipt that dotfiles had installed unpinned, and removed the
tool from the fleet updater's reach for good.

## Solution

Pin deliberately, in both directions, rather than fighting over the receipt. `git_uv_tools` are now
installed as `<name> @ git+<repo>@<newest release tag>` by `src/dotfiles/providers/uvtool.py`,
which is both halves — there was a second implementation in `install/common/lib/uv-git-tools.sh`
for `update.sh` until reconcile collapsed to one verb. Moving a pin
means reinstalling the requirement; `uv tool upgrade` cannot do it. Both dotfiles and the tools' own
updaters resolve the version from the GitHub releases API, so they cannot disagree about which
release is newest.

`tracks_branch: true` in packages.yml marks the exception — a repo publishing no releases has no tag
to pin, so it follows its default branch and is upgraded with `uv tool upgrade`.

Measuring the pin is the other half, and it landed much later. Until it did, `dotfiles` reported
every `git_uv_tools` entry converged for as long as its directory existed, so four tools sat months
behind while `plan` said there was nothing to do — the same blindness the receipt caused in the
updater, reproduced in the checker. These entries are compared against the releases cache like every
other section that installs from a named repo, and the *installed* side is read back from the
receipt rather than by running the tool: `uv tool install` does none of the version stamping a
release build does, so a tool that answers `--version` answers with whatever its source hardcodes,
and several of them cannot answer at all.

## Key Learnings

- **An unpinned git install is not the neutral default; it is a distinct, degraded state.**
  `pyselfupdate` treats a git requirement with no `rev=` as a dev checkout: it never prints an update
  notice and refuses to reinstall over it. Five tools installed by dotfiles had their own update
  notices silently disabled, which is why only syncer ever nagged.
- **"Already at latest" needs to mean "the newest release was resolved and compared to this one."**
  Reporting off a before/after diff of local state was an improvement over reporting off an exit
  code, but it still cannot see a no-op that was never going to do anything.
- **Pinning to releases means unreleased commits on `main` are deliberately not installed.** Cutting
  a release is what ships work to the fleet. The migration moved three tools back from `main` HEAD to
  their release tag; all the skipped commits were `ci:`/`docs:`/`style:`.
- **Two updaters writing the same receipt must agree on its shape.** Whichever ran last won, and the
  loser reported success either way.
