# cargo binstall Falls Back to Compiling, and That Is Usually Fine

## Problem

`cargo binstall` tries three sources in order — `crate-meta-data`,
`quick-install`, `compile`. The last is a source build, and it used to be taken
**silently**: no error, no output, just a long pause that could not be told from a
deadlock. That was the whole fault, and `providers/cargo.py` streams the call so
binstall's own `will be installed from source` and `Compiling` lines reach the
screen.

A compiled crate still converges the machine. Slow is not broken, and a tool does
not change its install method for being slow — every Rust CLI comes from
`cargo binstall` on every machine, and a second declaration for one platform costs
more than the build does.

**The one thing a source build genuinely breaks is the offline bundle.** The
bundler caches a binary upstream published, so a crate with nothing to cache
cannot ride along and the firewalled WSL box compiles it too. `tokei` is that
case, which is why it sits in `system_packages`: it stopped attaching release
binaries after `v13.0.0-alpha.0` and its stable tags carry zero assets.

## Solution

Ask binstall which source answers. It resolves exactly as an install would and
writes nothing:

```bash
cargo binstall --force --dry-run -y --targets <triple> <crate>
```

`--force` is what makes it answer: without it a crate at the resolved version
reports `already installed` and never says where the binary would come from.
`--targets` lets one machine answer for the whole portfolio.

**Counting a repo's assets answers the wrong question.** Upstream is only the
first source. `cargo-bins/cargo-quickinstall` builds binaries for crates whose
maintainers do not, and it covers `fnm`, `fd-find`, `eza` and `git-delta` on
x86_64 macOS where upstream publishes nothing at all.

If the answer is `will be installed from source`, that is information, not a
defect. Act on it only when the crate also has to reach a machine that installs
from the offline bundle.

## A binary restored from a bundle makes the source build fail

```text
error: binary `oxker` already exists in destination
Add --force to overwrite
ERROR Cargo errored! ExitStatus(unix_wait_status(25856))
```

**Read past the last four lines.** The refusal names `--force`, which reads as a
flag somebody forgot, and the two hosts that timed out are ten lines above it.
`providers/cargo._from_binstall` handles this and records why.

## Key Learnings

- A source build is visible and acceptable. Do not move a tool to another package
  manager to avoid one — that splits a declaration across two sections, leaves the
  old binary on every machine that already installed it, and buys a shorter
  install.
- "Written in Rust" does not imply "installable via cargo binstall", and neither
  does a populated asset list. What decides it is whether a prebuilt binary exists
  for the target, from any of the three strategies.
- A refused *download* host produces the same source build with every asset in
  place: the crates.io API and the release host are two hosts, and only the second
  has to be blocked. `dotfiles network check` says which half is answering.
- Cargo owning a binary is a fact with a receipt. `~/.cargo/.crates.toml` lists
  every binary cargo placed, and a file missing from it is one `cargo install`
  will not write over — which is what anything filling `~/.cargo/bin` by another
  route leaves behind.
