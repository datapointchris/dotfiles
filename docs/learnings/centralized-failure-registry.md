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
output_failure_data "yazi" "$url" "$version" "$reason" "$manual_steps"

# Parent's run_installer() parses stderr and appends to FAILURES_LOG
```

## Key Learnings

- One shared, append-only file beats per-script registries — PID isolation works against you here
- Export the log path from the parent so all children inherit it
- Make the registry optional: scripts check `${FAILURES_LOG:-}` before writing (backwards compatible)
- Dead code accumulates when function signatures change — 14 files referenced a `report_failure()` that never existed
- Test with network-restricted Docker containers to simulate corporate firewall behavior

## Related

- [Resilient Installation Patterns](resilient-installation-patterns.md)
- [WSL PowerShell Stdin Consumption](wsl-powershell-stdin-consumption.md)
