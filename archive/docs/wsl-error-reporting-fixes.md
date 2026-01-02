# WSL Installation Error Reporting and Testing Plan

**Created**: 2025-12-05
**Status**: Planning
**Priority**: High (production WSL is broken)

## Problem Summary

Based on real WSL installation failures from work computer:

### Current Issues

1. **Multiple separate log files** instead of one centralized failure log
   - Created: `dotfiles-installation-failures-20251205-132848.txt` (gpg-tui only)
   - Created: `dotfiles-installation-failures-20251205-132859.txt` (tenv only)
   - But 10+ other failures weren't logged at all

2. **Not all failures being reported to logs**
   - Failures from full-install-log.txt that weren't in failure reports:
     - Docker packages (apt failures)
     - Yazi (SSL certificate error)
     - Glow (SSL certificate error)
     - Duf (SSL certificate error)
     - Terraformer (SSL certificate error)
     - Terrascan (SSL certificate error)
     - Trivy (SSL certificate error)
     - zk (SSL certificate error)
   - Only gpg-tui and tenv were reported

3. **Script may be stopping on some failures**
   - Some GitHub release installers appear to be exiting instead of continuing
   - Need to verify all installers use proper error handling

4. **No consolidated summary at the end**
   - Individual installers display their own summaries
   - No single report of ALL failures

5. **Cannot test in realistic environment**
   - Corporate firewalls block github.com downloads
   - raw.githubusercontent.com is blocked
   - Need Docker-based testing with simulated network restrictions

## Root Cause Analysis

### Issue 1: Multiple Failure Registries

**Location**: `management/common/lib/install-helpers.sh:108-116`

```bash
init_failure_registry() {
  export DOTFILES_FAILURE_REGISTRY="/tmp/dotfiles-failures-$$"  # $$ = unique PID
  mkdir -p "$DOTFILES_FAILURE_REGISTRY"
  trap 'rm -rf "$DOTFILES_FAILURE_REGISTRY" 2>/dev/null || true' EXIT INT TERM
}
```

**Problem**: Each script that calls `init_failure_registry` creates a NEW registry:

- `cargo-tools.sh` → `/tmp/dotfiles-failures-12345`
- `tenv.sh` → `/tmp/dotfiles-failures-12346`
- Each has its own cleanup trap that removes the directory on exit

**Grep results showing 17 scripts calling init_failure_registry**:

- management/common/install/fonts/fonts.sh
- management/common/install/plugins/tmux-plugins.sh
- management/common/install/plugins/shell-plugins.sh
- management/common/install/plugins/nvim-plugins.sh
- management/common/install/github-releases/terraformer.sh
- management/common/install/github-releases/yazi.sh
- management/common/install/custom-installers/shellspec.sh
- management/common/install/custom-installers/awscli.sh
- management/common/install/custom-installers/claude-code.sh
- management/common/install/language-tools/go-tools.sh
- management/common/install/language-tools/npm-install-globals.sh
- management/common/install/language-tools/cargo-tools.sh
- management/common/install/language-managers/tenv.sh

### Issue 2: Individual Summary Displays

Each installer calls `display_failure_summary` at the end, which:

1. Shows only its own failures
2. Saves a separate timestamped report file
3. Happens before main install.sh can collect all failures

**Example from cargo-tools.sh**:

```bash
init_failure_registry  # Creates new registry
# ... install tools ...
display_failure_summary  # Shows only cargo tool failures, creates separate log
```

### Issue 3: GitHub Release Installer Library

**Location**: `management/common/lib/github-release-installer.sh`

Some installers use the shared library which has proper error handling, but not all failures call `report_failure()`.

**From full-install-log.txt** - SSL certificate errors:

```yaml
curl: (60) SSL certificate problem: unable to get local issuer certificate
[FATAL] ✗ Failed to download from https://github.com/...
[WARNING] ▲ yazi installation failed (see summary)
```

The installer shows warnings but may not be calling `report_failure()` correctly.

### Issue 4: Scripts with set -e

Many installers have `set -euo pipefail` which causes immediate exit on any error:

- 32 scripts found with `set -e` or `exit 1` in management/common/install/

The main `install.sh` uses `run_phase_installer()` wrapper with `|| true` to continue:

```bash
run_phase_installer "$github_releases/yazi.sh" "yazi" || true
```

But this doesn't guarantee the failure gets properly logged.

## Solution Design

### Phase 1: Centralize Failure Registry (Critical)

**Goal**: All failures report to ONE registry, one summary at the end

**Changes needed**:

1. **Main install.sh** (already correct at line 136):

   ```bash
   install_common_phases() {
       init_failure_registry  # ✓ Already does this
       # ... install everything ...
       display_failure_summary  # ✓ Already does this at line 226
   }
   ```

2. **Remove init/display from individual installers**:
   - Remove all `init_failure_registry` calls from child scripts
   - Remove all `display_failure_summary` calls from child scripts
   - Rely on parent registry (exported variable)

3. **Update install-helpers.sh** to handle missing registry gracefully:

   ```bash
   report_failure() {
       # Skip if no registry (running script standalone)
       if [[ -z "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
           log_warning "No failure registry - failure not tracked"
           return 0
       fi
       # ... existing code ...
   }
   ```

**Files to modify** (17 total):

- management/common/install/fonts/fonts.sh
- management/common/install/plugins/{tmux,shell,nvim}-plugins.sh
- management/common/install/github-releases/{terraformer,yazi}.sh
- management/common/install/custom-installers/{shellspec,awscli,claude-code}.sh
- management/common/install/language-tools/{go-tools,npm-install-globals,cargo-tools}.sh
- management/common/install/language-managers/tenv.sh

### Phase 2: Ensure All Failures Are Reported

**Goal**: Every installation failure calls `report_failure()`

**Changes needed**:

1. **GitHub release installers using library** (most common pattern):
   - Verify `github-release-installer.sh` calls `report_failure()` on download failures
   - Check all installers properly handle library errors

2. **Audit error paths in each installer**:

   ```bash
   # Current (some installers):
   if ! download_file "$url" "$output" "$tool"; then
       log_warning "Installation failed (see summary)"  # ❌ No report_failure()
       exit 1
   fi

   # Fixed:
   if ! download_file "$url" "$output" "$tool"; then
       report_failure "$tool" "$url" "$version" "$manual_steps" "Download failed"
       log_warning "$tool installation failed (details in summary)"
       exit 1
   fi
   ```

3. **Wrapper function enhancement** in install.sh:

   ```bash
   run_phase_installer() {
       local script="$1"
       local tool_name="$2"

       if bash "$script"; then
           return 0
       else
           local exit_code=$?
           # Check if failure was reported
           if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]] && \
              compgen -G "$DOTFILES_FAILURE_REGISTRY/*-${tool_name}.txt" > /dev/null 2>&1; then
               log_warning "$tool_name installation failed (details in summary)"
           else
               # Unreported failure - create generic entry
               report_failure "$tool_name" "unknown" "unknown" \
                   "Re-run: bash $script" \
                   "Installation script exited with code $exit_code"
               log_warning "$tool_name installation failed (see summary)"
           fi
           return 1  # ✓ Continue with || true in parent
       fi
   }
   ```

### Phase 3: Script Resilience (Continue on Errors)

**Goal**: No script should stop the entire installation

**Current approach** (already correct):

```bash
# install.sh already uses || true for resilience
run_phase_installer "$github_releases/yazi.sh" "yazi" || true
run_phase_installer "$github_releases/glow.sh" "glow" || true
```

**Verify**:

- All individual installers properly return non-zero on failure
- All callers use `|| true` to continue
- No child scripts call `exit 1` without proper cleanup

### Phase 4: Testing Environment

**Goal**: Docker-based testing that simulates corporate firewall restrictions

**Create**: `management/tests/test-install-wsl-network-restricted.sh`

**Architecture**:

```text
┌─────────────────────────────────────────────────┐
│ Docker Container (Ubuntu WSL rootfs)            │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │ Squid Proxy (Filtering)                   │  │
│  │  • Block: github.com/*/releases/*         │  │
│  │  • Block: raw.githubusercontent.com       │  │
│  │  • Block: api.github.com                  │  │
│  │  • Allow: archive.ubuntu.com (apt)        │  │
│  │  • Allow: crates.io (cargo)               │  │
│  └───────────────────────────────────────────┘  │
│                      ↓                           │
│  ┌───────────────────────────────────────────┐  │
│  │ Install Script                             │  │
│  │  • All GitHub downloads fail               │  │
│  │  • Apt packages work                       │  │
│  │  • Tests error handling                    │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Implementation Steps**:

1. **Base on existing test-install-wsl-docker.sh**
   - Copy structure
   - Add Squid proxy configuration

2. **Squid configuration** (`squid.conf`):

   ```text
   # Block GitHub release downloads
   acl blocked_github dstdomain .github.com
   acl blocked_raw dstdomain raw.githubusercontent.com
   acl blocked_api dstdomain api.github.com

   acl blocked_paths urlpath_regex /releases/download/

   # Allow apt repositories
   acl allowed_apt dstdomain .ubuntu.com
   acl allowed_crates dstdomain crates.io

   http_access deny blocked_github blocked_paths
   http_access deny blocked_raw
   http_access deny blocked_api
   http_access allow allowed_apt
   http_access allow allowed_crates
   http_access deny all
   ```

3. **Alternative: iptables-based blocking**

   ```bash
   # Simpler approach - block IPs for github.com
   docker exec "$CONTAINER" bash -c "
     # Block GitHub IPs (get current IPs)
     GITHUB_IPS=\$(dig +short github.com raw.githubusercontent.com api.github.com | grep -v '\.$')
     for ip in \$GITHUB_IPS; do
       iptables -A OUTPUT -d \$ip -j REJECT
     done
   "
   ```

4. **DNS-based blocking** (simplest):

   ```bash
   # Override DNS resolution in container
   docker exec "$CONTAINER" bash -c "
     echo '127.0.0.1 github.com' >> /etc/hosts
     echo '127.0.0.1 api.github.com' >> /etc/hosts
     echo '127.0.0.1 raw.githubusercontent.com' >> /etc/hosts
   "
   ```

5. **Test assertions**:

   ```bash
   # After running install.sh in restricted container:
   # 1. Verify failure log exists
   test -f /tmp/dotfiles-installation-failures-*.txt || fail "No failure log created"

   # 2. Count failures (should have ~8-10 GitHub tool failures)
   failure_count=$(grep -c "^TOOL=" /tmp/dotfiles-installation-failures-*.txt)
   [[ $failure_count -ge 8 ]] || fail "Expected 8+ failures, got $failure_count"

   # 3. Verify specific tools failed
   grep -q "TOOL='yazi'" /tmp/dotfiles-installation-failures-*.txt || fail "yazi failure not logged"
   grep -q "TOOL='glow'" /tmp/dotfiles-installation-failures-*.txt || fail "glow failure not logged"

   # 4. Verify apt packages still worked
   dpkg -l | grep -q build-essential || fail "apt packages didn't install"

   # 5. Verify only ONE failure log file
   failure_files=$(ls -1 /tmp/dotfiles-installation-failures-*.txt | wc -l)
   [[ $failure_files -eq 1 ]] || fail "Expected 1 failure log, found $failure_files"

   # 6. Verify summary was displayed (check install log)
   grep -q "Installation Summary" "$INSTALL_LOG" || fail "No summary displayed"
   ```

### Phase 5: Documentation

**Create**: `docs/learnings/wsl-network-restrictions.md`

Document:

- How corporate firewalls affect installation
- Which tools fail gracefully
- Manual installation workflow
- How to test in restricted environment

## Implementation Order

### Step 1: Fix Multiple Registries (Highest Priority) ✅ COMPLETED

**Goal**: Get all failures into one log file

1. ✅ Create test for current broken behavior
2. ✅ Remove init_failure_registry from 13 child scripts
3. ✅ Remove display_failure_summary from child scripts
4. ✅ Verify main install.sh handles everything
5. ✅ **CRITICAL FIX**: Enhanced report_failure() to print manual steps when no registry exists
   - Standalone runs: Print manual steps immediately
   - Parent runs: Add to registry for batch summary
   - Prevents UX regression where users see "failed (see summary)" with no summary
6. Pending: Test on macOS first (safe environment)

**Success criteria**:

- Only ONE `/tmp/dotfiles-installation-failures-*.txt` file created
- File contains ALL failures from entire installation
- ✅ Standalone script runs show manual installation steps immediately

### Step 2: Audit and Fix Unreported Failures

**Goal**: Ensure every failure is logged

1. Review each of the 10 failures from full-install-log.txt
2. Add report_failure() calls where missing
3. Test each installer in isolation
4. Verify failures appear in registry

**Success criteria**:

- Run restricted test (Step 4), count failures in log
- Should see 8-10 GitHub tool failures logged
- No "[WARNING] Installation failed" without corresponding log entry

### Step 3: Enhanced Error Context

**Goal**: Better error messages in failure reports

1. Add SSL certificate detection
2. Add corporate firewall hints
3. Improve manual installation instructions

**Success criteria**:

- SSL errors show helpful message about corporate CAs
- Manual steps are copy-pasteable
- Version numbers are accurate

### Step 4: Create Network-Restricted Test

**Goal**: Automated testing of firewall scenarios

1. Create test-install-wsl-network-restricted.sh
2. Implement DNS-based blocking (simplest approach)
3. Add test assertions
4. Integrate into CI (if applicable)

**Success criteria**:

- Test runs in <10 minutes
- Reliably fails GitHub downloads
- Apt and cargo still work
- Validates error reporting

### Step 5: Real-World Validation

**Goal**: Test on actual WSL work computer

1. Test fixed scripts on real WSL environment
2. Verify all failures are logged
3. Use manual installation instructions to complete setup
4. Document any edge cases

**Success criteria**:

- WSL system is fully functional
- No missing tools
- All failures were actionable

## Files to Create

1. `.planning/wsl-error-reporting-fixes.md` (this file)
2. `management/tests/test-install-wsl-network-restricted.sh` (new test)
3. `management/tests/lib/network-blocking.sh` (helper functions)
4. `docs/learnings/wsl-network-restrictions.md` (documentation)

## Files to Modify

### Critical (Phase 1)

1. `management/common/install/fonts/fonts.sh` - remove init/display
2. `management/common/install/plugins/tmux-plugins.sh` - remove init/display
3. `management/common/install/plugins/shell-plugins.sh` - remove init/display
4. `management/common/install/plugins/nvim-plugins.sh` - remove init/display
5. `management/common/install/github-releases/terraformer.sh` - remove init/display
6. `management/common/install/github-releases/yazi.sh` - remove init/display
7. `management/common/install/custom-installers/shellspec.sh` - remove init/display
8. `management/common/install/custom-installers/awscli.sh` - remove init/display
9. `management/common/install/custom-installers/claude-code.sh` - remove init/display
10. `management/common/install/language-tools/go-tools.sh` - remove init/display
11. `management/common/install/language-tools/npm-install-globals.sh` - remove init/display
12. `management/common/install/language-tools/cargo-tools.sh` - remove init/display
13. `management/common/install/language-managers/tenv.sh` - remove init/display

### Important (Phase 2)

14. `management/common/lib/github-release-installer.sh` - ensure report_failure() called
15. All scripts using github-release-installer.sh - verify error handling

### Enhancement (Phase 3)

16. `management/common/lib/install-helpers.sh` - improve error messages

## Testing Strategy

### Unit Tests

- Test report_failure() in isolation
- Test init_failure_registry only called once
- Test display_failure_summary aggregates all failures

### Integration Tests

1. **Baseline test** (existing): `test-install-wsl-docker.sh`
   - Run on clean WSL container
   - All downloads work
   - Verify no failures logged (or only expected ones)

2. **Network-restricted test** (new): `test-install-wsl-network-restricted.sh`
   - Block GitHub downloads
   - Verify 8-10 failures logged
   - Verify only ONE log file
   - Verify summary displayed
   - Verify apt packages still worked

3. **Real-world test**: Manual run on work WSL
   - Actual corporate firewall
   - Real SSL certificate issues
   - Test manual installation instructions

### Test Matrix

| Test | GitHub Blocked | Failures Expected | Log Files | Summary |
|------|----------------|-------------------|-----------|---------|
| Baseline | No | 0-2 | 1 | Yes |
| Restricted | Yes | 8-10 | 1 | Yes |
| Real WSL | Partial | 5-8 | 1 | Yes |

## Success Metrics

### Immediate (Phase 1-2)

- [ ] Only ONE failure log file created per installation
- [ ] All failures appear in that log file
- [ ] Summary shows all failures at the end
- [ ] Installation continues despite failures

### Medium-term (Phase 3-4)

- [ ] Network-restricted test passes
- [ ] Error messages are helpful and actionable
- [ ] Manual installation instructions work

### Long-term (Phase 5)

- [ ] WSL installation works on corporate network
- [ ] User can complete setup with manual steps
- [ ] No orphaned configuration or broken symlinks

## Risk Analysis

### Low Risk

- Removing init_failure_registry from child scripts
  - Mitigation: Scripts can still run standalone (they just won't log failures)
  - Fallback: Keep report_failure() null-safe

### Medium Risk

- Adding report_failure() calls might miss edge cases
  - Mitigation: run_phase_installer() catches unreported failures
  - Fallback: Generic "script failed" entries

### High Risk

- WSL system is currently broken on work computer
  - Mitigation: Test thoroughly on Docker first
  - Mitigation: Can manually run individual installers
  - Fallback: Fresh WSL install if needed

## Notes from Actual Failure Log

### Failures that were NOT logged (from full-install-log.txt)

1. Docker packages (apt) - lines 49-62
2. Yazi - line 129 (SSL cert)
3. Glow - line 144 (SSL cert)
4. Duf - line 160 (SSL cert)
5. Terraformer - line 181 (SSL cert)
6. Terrascan - line 196 (SSL cert)
7. Trivy - line 212 (SSL cert)
8. zk - line 228 (SSL cert)

### Failures that WERE logged

1. gpg-tui - line 316-500 (cargo-binstall timeout → compilation failure)
2. tenv - line 628 (SSL cert)

### Pattern Analysis

- Phase 5 (GitHub releases): 7/11 installers failed but only 0 were logged
- Phase 6 (Rust/Cargo): 1/1 failure was logged (gpg-tui)
- Phase 7 (Language managers): 1/1 failure was logged (tenv)

**Hypothesis**: GitHub release scripts are exiting without calling report_failure()

## Next Steps

1. Review this plan
2. Start with Step 1 (fix multiple registries)
3. Create test for current broken behavior
4. Implement fixes
5. Test on Docker
6. Deploy to real WSL
