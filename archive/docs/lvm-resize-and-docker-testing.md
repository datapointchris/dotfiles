# LVM Resize and Docker E2E Testing - Session Continuation

## Immediate Task: Resize LVM Root Partition

### Problem

Root partition is 20G, home is 932G. Docker/containerd store data on root by default, causing Docker containers to run out of space. Need root at 100G.

### Why TTY Approach Failed

`umount /home` fails because user session processes hold it open. `fuser -km /home` kills the desktop session but Hyprland restarts via TTY auto-login, re-mounting /home immediately.

### Solution: Boot from Arch Live USB

1. Boot the Arch install USB
2. Activate LVM: `vgchange -ay`
3. Run the resize commands without anything mounted:

```bash
# Check home filesystem first
e2fsck -f /dev/mapper/ArchinstallVg-home

# Shrink home filesystem + LV together
lvreduce -r -L 852G /dev/mapper/ArchinstallVg-home

# Grow root LV
lvextend -L 100G /dev/mapper/ArchinstallVg-root

# Check and grow root filesystem
e2fsck -f /dev/mapper/ArchinstallVg-root
resize2fs /dev/mapper/ArchinstallVg-root
```

1. Reboot into normal system
2. Verify: `df -h / /home` — root should be ~100G, home ~852G

### After Resize: Clean Up Docker Config

- Remove `/etc/docker/daemon.json` (the data-root workaround is no longer needed)
- Remove `/home/.docker-data` if it exists: `sudo rm -rf /home/.docker-data`
- Restart Docker: `sudo systemctl restart docker`
- Verify: `docker info | grep "Docker Root Dir"` should show `/var/lib/docker`

### Also: Remove Docker Data-Root from Arch Setup Script

The Docker data-root config in `management/arch/setup/system-config.sh` (lines 23-43) should be removed since root will have enough space. Keep only the docker group + socket enablement + containerd changes are NOT needed either.

---

## Context: What Was Being Tested

### Manifest-Driven Dotfiles Changes

A major refactor to make install.sh manifest-driven with `--machine` flag. All implementation is complete. Running e2e Docker tests to validate.

### Test Results So Far

- **Unit tests**: ALL PASS (BATS 39/39, pytest 52/52, symlinks 25/25)
- **Integration tests**: ALL PASS (BATS 108 non-Docker, app verification 33/33)
- **E2E Docker test**: Blocked by disk space — the reason for the LVM resize

### Changes Made This Session

**E2E test scripts updated** (all pass `--machine` to install.sh):

- `tests/install/e2e/arch-docker.sh` → `--machine arch-personal-workstation`
- `tests/install/e2e/wsl-docker.sh` → `--machine wsl-work-workstation`
- `tests/install/e2e/wsl-network-restricted.sh` → `--machine wsl-work-workstation`
- `tests/install/e2e/offline-docker.sh` → `--machine wsl-work-workstation`
- `tests/install/e2e/macos-temp-user.sh` → `--machine macos-personal-workstation`
- `tests/install/e2e/current-user.sh` → accepts `--machine` flag, passes through

**Arch system-packages.sh**: AUR packages skipped in Docker test mode (GUI-only apps)

**Arch setup script** (`management/arch/setup/system-config.sh`):

- Docker group + socket enablement
- Docker data-root config (REMOVE THIS after LVM resize)
- GDM disable
- TTY auto-login (moved from system-packages.sh, uses `whoami` instead of hardcoded `chris`)

**arch-docker.sh**: Reverted tmpfs workarounds (no longer needed once root is resized)

### After LVM Resize Is Done, Resume With

1. Clean up Docker config (remove daemon.json workaround + data-root code from setup script)
2. Re-run: `bash tests/install/e2e/arch-docker.sh -k`
3. Fix any remaining test failures
4. All changes still need to be committed
