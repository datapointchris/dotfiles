# Centralized Failure Registry

**Context**: WSL installation behind a corporate firewall had 10+ failures, but only 2 were logged — the rest were silently lost because each child script created its own failure registry.
**Date**: December 2025

## The Problem

The original design called `init_failure_registry()` in each child installer script, creating separate `/tmp/dotfiles-failures-$$` directories per script PID. Since each script ran in its own process, failures were scattered across multiple registries. Worse, the `report_failure()` function referenced in 14 installer files never actually existed — the conditional blocks were dead code.

Real-world result: installing on WSL behind a corporate firewall produced 8+ SSL certificate errors (yazi, glow, duf, terraformer, terrascan, trivy, zk, gpg-tui) but only gpg-tui and tenv were reported.

## The Solution

Single exported `FAILURES_LOG` file path from the parent process:

```bash
# Parent (install.sh) — creates ONE log file
FAILURES_LOG="/tmp/dotfiles-install-failures-$(date +%Y%m%d-%H%M%S).txt"
export FAILURES_LOG

# Child scripts output structured failure data to stderr
output_failure_data "yazi" "$url" "$version" "$reason" "$error_output"

# Parent's run_installer() parses stderr and appends to FAILURES_LOG
```

## The Follow-Up: A Logged Failure That Says Nothing

Capturing every failure was not enough. The report recorded a fixed `reason` string
chosen by the installer — "Download failed", "Failed to install via go install" — while the
error explaining *why* went to the console and was lost, because `run_installer` captured
only stderr and `go-tools.sh` printed go's error on stdout. Carried off the work machine,
the report named the tool and the step and nothing else.

Each installer also shipped a block of manual instructions that restated the download URL
and the PATH check already in the report. Identical across installers, useless after the
first read, and on the machine that actually fails — the one behind the corporate firewall —
"download it in your browser" is not something the reader can act on. Removed, and replaced
with `FAILURE_DETAIL_START/END` carrying the failing command's real output.

## Key Learnings

- One shared, append-only file beats per-script registries — PID isolation works against you here
- Export the log path from the parent so all children inherit it
- Make the registry optional: scripts check `${FAILURES_LOG:-}` before writing (backwards compatible)
- Dead code accumulates when function signatures change — 14 files referenced a `report_failure()` that never existed
- Test with network-restricted Docker containers to simulate corporate firewall behavior
- A hand-written `reason` can only name the step that failed. Always capture the failing
  command's own output — that is the only part of the report that identifies the cause
- Send that output to stderr, not stdout: the wrapper only captures stderr, so anything
  echoed to the console never reaches the file a person reads later
- Parse one report entry per `FAILURE_TOOL` record. A flat grep over stderr spliced two
  tools' fields into a single entry, and `go-tools.sh` fails several tools in one run
- Tests that reimplement the wrapper instead of sourcing it verify a format nothing produces

## Related

- [Resilient Installation Patterns](resilient-installation-patterns.md)
- [WSL PowerShell Stdin Consumption](wsl-powershell-stdin-consumption.md)
