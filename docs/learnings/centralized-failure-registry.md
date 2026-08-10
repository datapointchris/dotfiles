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

## The Second Follow-Up: A Fix Applied Three Places Out of Seven

The next WSL run still produced a nameless entry — `tmux-plugins` as a heading with nothing
beneath it. Two causes, both survivors of the previous round.

The installer piped TPM into a reader loop, so under `set -o pipefail` a failing TPM aborted
the script *at the pipeline*, before the branch that calls `output_failure_data`. No record
was emitted at all. The loop had also re-emitted TPM's output through `log_info`, onto
stdout, where the wrapper cannot see it — the same stdout-versus-stderr mistake as
`go-tools.sh`, in a second file.

The deeper problem was the shape of the previous fix: three call sites were passed their
error output by hand and the remaining four were left to a fallback that scrapes unattributed
stderr. That fallback deliberately declines to fire when a script reports more than one tool,
because there is no way to say which one produced the output — and every one of the four
left behind loops over packages. The fallback could never have covered them.

## Key Learnings

- One shared, append-only file beats per-script registries — PID isolation works against you here
- Export the log path from the parent so all children inherit it
- Make the registry optional: scripts check `${FAILURES_LOG:-}` before writing (backwards compatible)
- Dead code accumulates when function signatures change — 14 files referenced a `report_failure()` that never existed
- Test with network-restricted Docker containers to simulate corporate firewall behavior
- A hand-written `reason` can only name the step that failed. Always capture the failing
  command's own output — that is the only part of the report that identifies the cause
- Capture both streams. Which one an installer's error lands on is not something the
  installer's author controls — go prints on stdout, curl on stderr — so a wrapper that
  captures one of them loses causes at random. (This one cost two rounds of fixes before the
  channels were separated by *kind* instead: see below.)
- Keep one report entry per failure. A flat grep over the whole output spliced two tools'
  fields into a single entry, and `go-tools.sh` fails several tools in one run
- Tests that reimplement the wrapper instead of sourcing it verify a format nothing produces
- Never pipe a command whose failure you intend to report — under `set -o pipefail` the
  script dies at the pipeline and the reporting branch below it never runs. Redirect to a
  file, capture the status with `|| status=$?`, then read the file
- A fallback that cannot fire for the common case is not coverage. Fixing the loud call
  sites by hand and trusting a fallback for the rest left four multi-package installers
  reporting no cause, because the fallback refuses to guess among several tools
- When nothing was captured, say so in the report. A blank entry cannot be told apart from
  the report having dropped the failure, and the reader re-runs the install to find out which

## What Replaced It

Every round above fought the same root cause: records and human text shared stderr, so each
consumer had to filter for the other. The wrapper stripped `FAILURE_*` lines out of what it
displayed, captured output had to have markers stripped so it could not forge a record, and
telling several failures apart needed an awk state machine.

Records went to a JSON file named by `$FAILURE_RECORDS`, which left stdout and stderr carrying
only what a person reads — so they were merged, shown live, and kept whole for the report. The
stdout-versus-stderr trap that caused two of the rounds above could not recur, because nothing
decided anything based on which of the two a line arrived on.

**The whole mechanism is gone as of 2026-08-10**, and the lesson outlived it. Every record above
described one bash installer's failure, and there are no bash installers: each is a provider
returning an `Outcome`, and `apply` writes those to its run record like every other verb. The
same rule holds in the new shape and is what made the old one necessary — a value returned is
never a value parsed back out of a stream. `dotfiles report latest` is where the failures are
read; `$FAILURE_RECORDS`, `failure-logging.sh`, `failure_report.py` and the `/tmp` failures log
are all retired.

## Related

- [Resilient Installation Patterns](resilient-installation-patterns.md)
- [WSL PowerShell Stdin Consumption](wsl-powershell-stdin-consumption.md)
