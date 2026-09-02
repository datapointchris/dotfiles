# Profiling Zsh Startup

**Context**: New shells intermittently took 6+ seconds to open. `ZSHRC_DEBUG=1` printed which steps ran but not how long any of them took, so the stall was invisible.
**Date**: July 2026

## The Problem

The stall was intermittent — roughly one shell in every two-minute window, with the rest opening in 0.4s. Averaging hid it, and because the slow shells were the ones actually opened by hand, every shell *felt* slow.

Two properties made it hard to find. The cost was wall-clock, not CPU (6.7s elapsed against 0.5s of user+sys), so it was blocking on the network rather than computing. And `ZSHRC_DEBUG` listed steps without timings, so it confirmed everything loaded while saying nothing about what was slow.

The culprit was `todoui completion zsh`. `todoui` reconciles with its API before any command that reads local data, exempting a denylist that included `completion` — but cobra gives `completion` a subcommand per shell, so the leaf executed is named `zsh` and never matched. Every shell paid a full API pull whenever the last one had gone stale.

## The Solution

Timing belongs inside `log()`, not at the call sites. One change gives every existing entry step and cumulative milliseconds, and the file stays as readable as it was:

```zsh
log() {
  flag_enabled ZSHRC_DEBUG 0 || return 0
  local now=$EPOCHREALTIME
  printf "  $CHECK_MARK %6.0fms %7.0fms  %-6s : %s\n" \
    $(( (now - ZSHRC_LAST) * 1000 )) $(( (now - ZSHRC_START) * 1000 )) "$1" "$2"
  ZSHRC_LAST=$now
  return 0
}
```

The offending step then names itself: `5933ms Setup : todoui completions`.

For anything `ZSHRC_DEBUG` cannot reach — `.zshenv`, `/etc/zshrc`, plugin init, or a stall between two logged steps — trace the whole startup instead. `PS4` accepts prompt escapes, so `%D{%s.%6.}` timestamps every line without needing `zsh/datetime` loaded first:

```bash
PS4='+%D{%s.%6.} %N:%i> ' zsh -ix -c exit 2>trace.log
awk '/^\+[0-9]{10}\./ {
  t=substr($1,2)+0
  if (prev>0 && t-prev>0.2) printf "%8.0fms BLOCKED AT: %s\n", (t-prev)*1000, prevline
  prev=t; prevline=$0
}' trace.log
```

Run that in a loop until a slow start is caught, since an intermittent stall will not appear on demand.

Generated blocks are cached and keyed on the tool's binary mtime, so each is regenerated only after that tool is upgraded. Caching is not the same as not paying, though: a cached file still costs its whole size to source, and `ruff` and `uv` generate 668K and 516K of clap definitions. So a block that *can* be autoloaded is written to `$XDG_CACHE_HOME/zsh/functions/` as `_<tool>`, where compinit indexes it and zsh reads the body only when Tab asks. Everything else is sourced from `$XDG_CACHE_HOME/zsh/completions/`.

What decides it is the generator's output, not the kind of thing it is. An autoloadable file has `#compdef` as its literal first line, and re-dispatches when `$funcstack[1]` is its own name — cobra and clap emit both, Typer emits neither, and doit emits only the first. Typer's leading blank line is the whole difference between a completion that works and one compinit silently skips.

Force a rebuild by deleting either directory, and the dump with them:

```bash
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/zsh"/{functions,completions,zcompdump-*}
```

compinit will not notice a change on its own. It reuses its dump on a **file count and a zsh version** — `#files: N  version: X`, compared against what is on fpath — and reads no mtime anywhere, so a tool upgraded in place is served from a dump written before the upgrade. `.zshrc` unlinks the dump itself whenever a generator actually rewrote a file.

`zsh-startup time` is the wall clock the trace above cannot see, and `zsh-startup steps` prints one `ZSHRC_DEBUG` run sorted by cost.

## Key Learnings

- Wall-clock far exceeding user+sys means blocking on I/O or network, not slow code — measure both before optimizing anything
- A debug flag that reports *what ran* but not *how long* cannot find a performance bug; timing in the logger costs one function and no call-site churn
- Intermittent stalls need a catch loop, not a single run — a mean across runs hides the tail that users actually experience
- `zsh -i -c exit` skips prompt rendering and `zsh-vi-mode`'s deferred init; use a PTY (`script -q /dev/null zsh -i`) when those are suspect
- Shell startup is a poor place to shell out to networked tools; cache generated completions against the binary's mtime instead

## Related

- [Shell Libraries](../architecture/shell-libraries.md)
