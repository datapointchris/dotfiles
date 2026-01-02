# VM Testing Plan

**Purpose**: Test dotfiles installation on fresh systems to ensure reproducibility and catch platform-specific issues.

**Last Updated**: 2025-11-04

---

## Overview

Testing dotfiles installation in virtual machines ensures:

- Installation scripts work on fresh systems
- Dependencies are correctly specified
- Cross-platform compatibility
- No reliance on existing system configuration
- Documentation is accurate and complete

---

## Testing Platforms

### Priority 1: macOS (Intel)

**Primary development platform**

**VM Setup**:

- Use UTM or Parallels Desktop
- Fresh macOS installation (matching primary system version)
- Minimal initial setup (just create user account)

### Priority 2: Ubuntu WSL

**Work computer environment**

**VM Setup**:

- Windows 11 with WSL2 enabled
- Fresh Ubuntu 24.04 LTS installation
- No pre-installed development tools

### Priority 3: Arch Linux

**Future personal system**

**VM Setup**:

- Arch Linux ISO installation
- Minimal base system (base, base-devel, linux, linux-firmware)
- Network configured

---

## Test Scenarios

### Scenario 1: Complete Fresh Install

**Goal**: Verify full installation from scratch

**Steps**:

1. Clone dotfiles repository
2. Run platform-specific bootstrap script
3. Verify all packages installed
4. Verify symlinks created
5. Test key functionality (shell, nvim, tmux)
6. Document any errors or issues

**Expected Duration**: 20-30 minutes per platform

### Scenario 2: Update Existing Installation

**Goal**: Verify update process works correctly

**Steps**:

1. Start from completed Scenario 1 VM
2. Simulate package list changes (add/remove from config)
3. Run `task update`
4. Verify changes applied correctly
5. Test that existing configuration preserved

**Expected Duration**: 10-15 minutes per platform

### Scenario 3: Symlink Management

**Goal**: Verify symlink creation/recreation works

**Steps**:

1. Start from completed Scenario 1 VM
2. Add new config file to dotfiles
3. Run `task symlinks:relink`
4. Verify new symlink created
5. Remove config file
6. Run `task symlinks:relink`
7. Verify symlink removed

**Expected Duration**: 5-10 minutes

### Scenario 4: Selective Installation

**Goal**: Verify individual component installation

**Steps**:

1. Fresh VM (no dotfiles)
2. Test individual installation tasks:
   - `task brew:install-all` (macOS)
   - `task nvm:install-node`
   - `task npm:install-all`
   - `task uv:install-all`
   - `task shell:install`
3. Verify each component works independently

**Expected Duration**: 15-20 minutes per platform

---

## VM Management

### Creating Test VMs

#### macOS (UTM)

```bash
# Download macOS recovery image
# Create VM in UTM with:
# - 4GB RAM
# - 64GB disk
# - Shared clipboard
# - Name: "dotfiles-test-macos"
```

#### Ubuntu WSL

```powershell
# Install fresh WSL distribution
wsl --install -d Ubuntu-24.04

# Export clean state for testing
wsl --export Ubuntu-24.04 C:\VMs\ubuntu-clean.tar

# Import for testing
wsl --import dotfiles-test C:\VMs\dotfiles-test C:\VMs\ubuntu-clean.tar
```

#### Arch Linux (UTM/VirtualBox)

```bash
# Download Arch ISO from archlinux.org
# Create VM with:
# - 2GB RAM
# - 32GB disk
# - Name: "dotfiles-test-arch"
```

### Snapshotting Strategy

**Initial Snapshots**:

1. **Fresh Install**: Right after OS installation, before any setup
2. **Prerequisites Installed**: After package manager and git installed
3. **Dotfiles Cloned**: After repository cloned
4. **Installation Complete**: After successful full installation

**Naming Convention**:

```
<platform>-<state>-<date>

Examples:
macos-fresh-2025-11-04
ubuntu-prerequisites-2025-11-04
arch-complete-2025-11-04
```

### Snapshot Management Commands

#### UTM

- Snapshots managed via GUI
- Before each test, revert to appropriate snapshot
- After successful test, create new snapshot

#### WSL

```bash
# Export current state
wsl --export dotfiles-test C:\VMs\snapshots\dotfiles-test-<state>.tar

# Restore from snapshot
wsl --unregister dotfiles-test
wsl --import dotfiles-test C:\VMs\dotfiles-test C:\VMs\snapshots\dotfiles-test-<state>.tar
```

---

## Testing Checklist

### Pre-Test Preparation

- [ ] VM snapshot created/reverted
- [ ] Testing notes document ready
- [ ] Screen recording started (optional)
- [ ] Time tracking started

### During Test

- [ ] Document every command executed
- [ ] Screenshot any errors
- [ ] Note execution times
- [ ] Record unexpected behavior
- [ ] Test with both `task` commands and manual methods

### Post-Test Verification

- [ ] All expected packages installed
- [ ] Symlinks correctly created
- [ ] Shell loads without errors
- [ ] neovim launches and LSPs work
- [ ] tmux configurations applied
- [ ] Tools command works (`tools list`, `tools show bat`)
- [ ] Git configuration correct (user, email, editor)
- [ ] PATH set correctly
- [ ] Shell completions work

### Post-Test Cleanup

- [ ] Testing notes saved to `docs/testing/YYYY-MM-DD-<platform>-<scenario>.md`
- [ ] Issues documented in GitHub issues or TODO
- [ ] Snapshot created if successful
- [ ] VM shut down properly

---

## Testing Schedule

**Initial Testing** (Phase 3 completion):

- Test all scenarios on macOS (primary platform)
- Basic fresh install test on WSL
- Document results and fix issues

**Regular Testing** (ongoing):

- After major changes: Full test suite on primary platform
- Monthly: Rotation of one full platform test
- Before releases: All platforms, all scenarios

**Automated Testing** (future):

- GitHub Actions for syntax validation
- Brewfile validation
- YAML config validation
- Shellcheck on scripts

---

## Test Result Documentation

### Test Report Template

```markdown
# Test Report: <Platform> - <Scenario>

**Date**: YYYY-MM-DD
**Platform**: macOS/WSL/Arch
**Scenario**: Fresh Install/Update/etc.
**Duration**: XX minutes
**Result**: ✅ PASS / ❌ FAIL / ⚠️ PARTIAL

## Environment
- OS Version:
- VM Software:
- Snapshot Used:

## Steps Executed
1. Step 1...
2. Step 2...

## Errors Encountered
### Error 1
- **Message**:
- **Cause**:
- **Fix**:

## Observations
- Unexpected behavior:
- Performance notes:
- Improvement suggestions:

## Verification Results
- [ ] Packages installed
- [ ] Symlinks created
- [ ] Shell loads
- [ ] Neovim works
- [ ] Tools available

## Conclusion
Summary of test outcome...

## Next Steps
- [ ] Issue to fix...
- [ ] Documentation update...
```

### Storage Location

```
docs/testing/
├── 2025-11-04-macos-fresh-install.md
├── 2025-11-04-wsl-fresh-install.md
├── 2025-11-05-macos-update-test.md
└── README.md  # Index of all test reports
```

---

## Common Issues to Watch For

### macOS

- Homebrew installation PATH issues
- Xcode Command Line Tools prompts
- Permissions for symlinks in system directories
- Conflicting system Python with brew Python

### WSL

- Windows PATH pollution
- Different package names (batcat vs bat, fdfind vs fd)
- systemd not enabled by default
- File permissions on Windows filesystem mounts

### Arch Linux

- AUR helper not installed
- Missing base-devel for building packages
- systemd services not enabled
- Desktop environment differences

---

## Dry Run Testing

Before VM testing, use dry-run tasks to verify logic:

```bash
# Test installation logic without making changes
task dry-run:install:macos

# Check what would be installed
brew bundle check --file=Brewfile --verbose

# Verify symlinks without creating them
task symlinks:verify
```

---

## Continuous Improvement

After each test:

1. Update this document with new findings
2. Add new test scenarios for edge cases discovered
3. Improve automation based on manual test pain points
4. Update installation scripts to handle discovered issues
5. Add checks to prevent recurring issues

---

## Future Enhancements

**Phase 4**: Implement automated testing

- GitHub Actions for validation
- Docker containers for Linux testing
- Automated report generation

**Phase 5**: Improve test coverage

- Test with different package versions
- Test upgrade paths (old dotfiles → new dotfiles)
- Test partial installations (skipping components)

**Phase 6**: Performance testing

- Measure installation time
- Track package download sizes
- Optimize slow steps

---

## Resources

- [UTM Documentation](https://docs.getutm.app/)
- [WSL Documentation](https://docs.microsoft.com/en-us/windows/wsl/)
- [Arch Installation Guide](https://wiki.archlinux.org/title/Installation_guide)
- [Taskfile Documentation](https://taskfile.dev/)

---

**Next Steps**:

1. Create initial VM snapshots for each platform
2. Run Scenario 1 (Fresh Install) on macOS
3. Document results
4. Fix any issues found
5. Iterate

**Success Criteria**:

- All three platforms install successfully from fresh state
- Zero manual interventions required
- Installation completes in under 30 minutes
- All post-test verifications pass
