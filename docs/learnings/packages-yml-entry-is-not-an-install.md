# A packages.yml Entry Is Not an Install

## Problem

The offline WSL work box died at the node phase with `fnm not found`, even though
`fnm` had a full `cargo_packages` entry in `packages.yml` — github repo, binary
pattern, description, tags. Three independent faults stacked up behind that one
message:

1. **No manifest listed it.** Every manifest spells out its `cargo_packages`, and
   none of them named `fnm`, so the cargo phase never had it to install. An entry
   in `packages.yml` only describes *how* a tool installs; the manifest decides
   *whether* it installs on this machine.
2. **The bundle could not have downloaded it anyway.** `{target}` expands to a Rust
   target triple, and fnm names its assets after the OS word — `fnm-linux.zip`,
   `fnm-macos.zip` — so the URL would have 404'd. The zip repackager also assumed
   broot's fat-zip layout (a target-named subdirectory) and could not see a binary
   sitting at the archive root.
3. **`install.sh` could not see it once installed.** It put only `~/.local/bin` on
   PATH, while `update.sh` carried the full set, so a phase consuming what an
   earlier phase installed to `~/.cargo/bin` worked on update and failed on install.

Offline made the stack visible because `cargo binstall` cannot paper over a missing
bundle entry when there is no network to fall back on.

## Solution

Adding to `packages.yml` is half the change — add the tool to the manifests that
need it, and check the asset name the bundler will construct actually exists:

```bash
gh api repos/<owner>/<repo>/releases/latest --jq '.tag_name, (.assets[].name)'
```

`linux_target` and `darwin_target` override the triple for tools named some other
way. PATH for both entry points now lives in `install/tool-path.sh`, sourced by
each, so they cannot diverge again.

## Key Learnings

- packages.yml describes an install; a manifest requests one. A tool in the first
  and none of the second is dead configuration that reads as working.
- A phase that consumes what an earlier phase installed is an ordering *and* a PATH
  dependency — the installers never read `.zshenv`.
- Test the invariant, not the instance: `tests/resolver/test_validate.py` asserts
  that any manifest with `npm_globals` also installs fnm, read off disk rather than
  from a list of names, so a new manifest is covered the day it is written.
- Anything the bundler only exercises for one tool (a zip layout, a naming scheme)
  should be a function with unit tests, not an inline block that has never met a
  second shape.
