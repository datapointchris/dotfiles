# Testing Bootstrap Dependencies

## Context

Bootstrap dependencies are packages that must be installed before other installation scripts can run. In our case, `python3-pyyaml` is required before `parse-packages.py` can parse the package list.

## The Problem

Installation failed on fresh WSL during Phase 1 (system packages) with:

```bash
# wsl.yml:43 - Wrong package name
sudo apt install -y python3-yaml  # Package doesn't exist

# wsl.yml:46 - Script tries to run immediately after
python3 parse-packages.py --type=system --manager=apt
# ImportError: No module named 'yaml'
```

**The test suite passed but real installation failed** because:

1. Wrong package name: `python3-yaml` instead of `python3-pyyaml`
2. **Test environment (Multipass Ubuntu cloud image) had `python3-pyyaml` pre-installed**
3. Even though bootstrap step tried to install wrong package, script could still run
4. Fresh WSL installations don't have PyYAML pre-installed, exposing the bug

## The Solution

**Root Fix: Use System Python Explicitly**

To ensure parse-packages.py works across all platforms regardless of which Python is in PATH:

**1. Use system Python via shebang** (`management/parse-packages.py:1`):

```python
#!/usr/bin/python3  # System Python, not #!/usr/bin/env python3
```

This ensures the script always uses `/usr/bin/python3` even if uv-managed Python is in PATH.

**2. Install PyYAML for system Python on each platform**:

WSL/Debian (`management/taskfiles/wsl.yml:43`):

```bash
sudo apt install -y python3-pyyaml  # Correct package name
```

Arch Linux (`management/packages.yml`):

```yaml
- name: python3-yaml
  pacman: python-yaml
```

macOS (`management/taskfiles/macos.yml`):

```bash
/usr/bin/python3 -m pip install --user PyYAML
```

**3. Use Docker with WSL rootfs for testing** (`management/test-wsl-docker.sh`):

```bash
# Download official WSL Ubuntu rootfs (one-time, cached)
curl -L https://cloud-images.ubuntu.com/wsl/noble/current/ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz

# Import into Docker (100% exact WSL environment, 563 packages)
gunzip -c ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz | docker import - wsl-ubuntu:24.04

# Run tests in authentic WSL environment
./management/test-wsl-docker.sh
```

This provides **100% accurate testing** - if it fails in the test, it will fail in WSL. If it passes in the test, it will pass in WSL.

**4. Verify the script works** (`management/verify-installation.sh:322`):

```bash
if python3 "$HOME/dotfiles/management/parse-packages.py" --type=system --manager=apt >/dev/null 2>&1; then
  print_success "parse-packages.py: working (yaml module available)"
else
  print_error "parse-packages.py: FAILED (yaml module missing)"
fi
```

Defense in depth - catches issues even if test environment differs.

## Key Learnings

**Use the exact production environment for testing**: Don't guess what's different - use official images. For WSL, Microsoft publishes the actual WSL rootfs that Docker can import. This eliminates all guesswork and provides 100% accurate testing.

**Test environments often differ from production in subtle ways**:

- Multipass Ubuntu cloud images: ~426 packages
- Docker ubuntu:24.04: ~100-150 packages
- WSL Ubuntu 24.04: 563 packages (official rootfs)

These differences cause tests to pass when they shouldn't.

**Bootstrap failures happen during installation, not verification**: The installation should fail immediately when trying to use a missing dependency. If your test passes but production fails during Phase 1, your test environment differs from production.

**Containers > VMs for testing**: Docker with official rootfs is faster, lighter, and more accurate than VMs with approximated environments. Startup time is seconds vs minutes.

**Package names vary across platforms**:

- Ubuntu/Debian: `python3-pyyaml` (system package via apt)
- Arch Linux: `python-yaml` (system package via pacman)
- macOS: `PyYAML` (installed via pip --user to system Python)

**Defense in depth**: Even with perfect test environment, add verification checks that test functionality (not just presence) to catch edge cases.

## Testing Approach

Best practice for testing system installations:

1. **Use official production images**: Download actual WSL rootfs, not approximations
2. **Docker for WSL testing**: Fast, lightweight, 100% accurate
3. **Install dependencies correctly**: Use proper package names for target platform
4. **Let `set -e` catch errors**: Installation fails immediately on first error
5. **Add verification checks**: Defense in depth for edge cases
6. **Document environment specs**: Record package counts and key differences if using alternatives

## Docker vs VM Comparison

| Aspect | Docker + WSL Rootfs | Multipass Cloud Image |
|--------|-------------------|---------------------|
| Accuracy | 100% (563 packages) | ~75% (426 packages) |
| Startup | <5 seconds | 1-2 minutes |
| Resources | Lightweight | VM overhead |
| Cleanup | Instant | 10-20 seconds |
| Use Case | Primary testing | Backup/fallback |

## Related

- `management/test-wsl-docker.sh` - Docker-based WSL testing (recommended)
- `management/wsl-docker-images.sh` - Manage WSL Docker images
- `management/test-install.sh` - Multipass testing (alternative)
- `management/taskfiles/wsl.yml` - Bootstrap package installation
- `management/verify-installation.sh` - Installation verification
- `management/parse-packages.py` - Package list parser
- `docs/development/testing.md` - Testing documentation
