# Go Was on No PATH, and Nothing Said So

## Problem

`dotfiles apply` on macOS reported the same thing on every run:

```text
✗ packages    1 item(s) need a person  ·  1 differ, 18 unmeasured
    unknown     go/forge     forge is installed but would not report a version
    unknown     go/sesh      sesh is installed but would not report a version
    missing     go/fleet     fleet is not on PATH
```

Eighteen Go tools reported `unknown`, which carries `Repair.NONE` — so `apply`
never upgraded any of them. `forge` sat eight minor versions behind while the row
read as merely unmeasurable. `gopls` was dead in every Go repo on the machine:

```text
failed to load view for file:///Users/chris/tools/toolbox: err: go command
required, not found: exec: "go": executable file not found in $PATH
```

And `go/fleet` failed on every apply:

```text
go: github.com/datapointchris/fleet@v1.18.0: verifying module: reading
https://sum.golang.org/lookup/github.com/datapointchris/fleet@v1.18.0: 404 Not Found
```

## Solution

Three independent faults, sharing one seam.

**`/usr/local/go/bin` was on no PATH.** `.zshenv` never named it, and `.zshrc`
added it in its non-darwin branch only — a leftover from when macOS took Go from
brew. Go's location is not platform-specific: go.dev unpacks to `/usr/local/go` on
both systems and `toolchain.GO_ROOT` has no branch. `.zshenv` now names it, and
`.zshrc` adds it outside the `$OSTYPE` test.

**The measurement asked PATH.** `gotool.installed_modules` called
`shutil.which('go')`, so it measured the shell that launched the run. It now asks
`toolchain.go_command`, which prefers the Go this repo unpacked. That fixes the
other half of the same fault on Arch, where an ssh command resolves the pacman
`/usr/bin/go` at go1.26.6 while `GO_ROOT` holds go1.26.5.

**`GONOSUMDB` was written only by `install_go`.** `fleet` is private, so the public
checksum database cannot read it and 404s; `GONOSUMDB` is what skips that lookup.
The only writer ran when Go was installed or below its floor, and a floor of
`1.23` against an installed `1.26.5` means never. It is now measured every run by
the `toolchains` resource and repaired by `apply`.

## Key Learnings

- **A fact written once at install is not converged state.** Everything else here
  is declare, measure, repair. These two — a PATH entry and a `go env` setting —
  were side effects of an install that no longer runs.
- **`put_on_path` hides exactly this.** It repairs PATH inside the process, so
  installs kept working on a machine whose PATH was wrong. Only the measurement
  path, which never called it, showed the damage.
- **A skip in a test is a hole the size of the thing it skips.** The test binding
  `.zshenv` to `TOOL_PATH_DIRS` skipped every `/usr` entry, and the one wrong entry
  was `/usr/local/go/bin`.
- **The e2e containers were right, which is why nobody noticed.** The harness
  builds its PATH from `TOOL_PATH_DIRS`, which named the directory all along.
- **Read the indentation in a Go error.** The `could not read Username` and
  `/tmp/gopath` in that 404 are under `server response:` — they describe Google's
  sumdb, not this machine. Local `git ls-remote` on the same private repo exits 0.
