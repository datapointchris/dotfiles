# cargo binstall Needs Upstream Release Binaries

## Problem

Consolidating Rust CLI tools into `cargo_packages` (installed via `cargo binstall`)
looks like it should apply uniformly to every Rust tool. It does not. `cargo
binstall` only fetches **prebuilt binaries** that upstream attaches to GitHub
releases (or a comparable host). When a crate ships no release binaries, binstall
silently falls back to `cargo install`, which **compiles from source**.

`tokei` is the trap. It is written in Rust, so it seems like an obvious fit — but
XAMPPRocky/tokei stopped attaching release binaries after `v13.0.0-alpha.0`. Its
current stable tags carry zero assets. Moving it to `cargo_packages` therefore:

- compiles ~200 crates from source on every workstation install (slow), and
- **cannot be carried in the offline bundle at all** — the bundler can only cache a
  binary upstream actually published, so the firewalled WSL work box compiles it
  from source too.

Measured on that box 2026-08-07 with `dotfiles network check`: crates.io is
**reachable**, and GitHub *release asset downloads* are **blocked** while the
release API is not. So the compile does succeed there — an earlier
reading claiming no crates.io access was wrong. The consequence is subtler than a
hard failure: `cargo binstall` can resolve any crate but cannot download a single
prebuilt binary, so on that machine it silently falls back to source builds for
*every* cargo package unless the bundle carries them.

Contrast `ripgrep`, which ships prebuilt binaries for every target on each release —
it moves to `cargo binstall` cleanly and even works on minimal LXC servers.

## Solution

Before moving a Rust tool into `cargo_packages`, confirm upstream ships release
binaries for the targets you install:

```bash
gh api repos/<owner>/<repo>/releases/latest --jq '.tag_name, (.assets[].name)'
```

No matching assets → keep it in `system_packages` (pacman/brew ship maintained
binaries) and leave a comment on the entry explaining why, so the consolidation
isn't attempted again.

## Key Learnings

- "Written in Rust" does not imply "installable via cargo binstall" — the deciding
  factor is whether **upstream publishes prebuilt release binaries**, not the language.
- binstall's fallback to source compilation is silent; it turns a fast binary install
  into a slow (or, offline, impossible) build without erroring up front.
- Verify release assets with the `gh api` one-liner above before reclassifying a tool.
- A tool that installs fine on your workstation can still break the offline WSL bundle —
  always reason about the most-constrained machine before moving install methods.
