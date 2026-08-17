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

The failure mode to know is the quiet one, and it does not need the registry to be
unreachable. `cargo binstall` resolves a crate's version through the crates.io API
and then fetches the binary from wherever the project publishes its releases —
two different hosts, and only the second one has to be refused. When it is,
binstall resolves every crate and downloads no prebuilt binary at all, falling
back to a source build for *every* cargo package rather than failing. Run
`dotfiles network check` on the machine in question if you need to know which half
is answering.

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
