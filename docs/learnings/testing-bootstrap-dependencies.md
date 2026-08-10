# Testing Bootstrap Dependencies

## The Problem

Installation failed on fresh WSL during system packages with:

```bash
# Wrong package name
sudo apt install -y python3-yaml  # Package doesn't exist

# The script runs immediately after
python3 parse_packages.py --type=system --manager=apt
# ImportError: No module named 'yaml'
```

A bootstrap dependency is a package that must be present before the thing that
reads the package list can run at all — so getting it wrong fails before any of
the machinery that would report it well exists.

**The test suite passed but real installation failed** because:

1. Wrong package name: `python3-yaml` instead of `python3-pyyaml`
2. **Test environment (Multipass Ubuntu cloud image) had `python3-pyyaml` pre-installed**
3. Even though bootstrap step tried to install wrong package, script could still run
4. Fresh WSL installations don't have PyYAML pre-installed, exposing the bug

## The Solution

**The bootstrap is gone, and that is the fix.** The CLI installs as a uv tool with
its dependencies declared, so there is no step that needs PyYAML to be true of the
machine beforehand, and no interpreter to choose between. The reader that needed
it — `parse_packages.py` — was deleted with the last installer bash.

What follows is the fix *as it stood*, because the shape of it is the reusable part
and the "goes away on Ubuntu 26.04" section below is only legible against it: the
answer at the time was to pin the interpreter and then guarantee the dependency on
each platform, one platform at a time.

**1. Use system Python via shebang**:

```python
#!/usr/bin/python3  # System Python, not #!/usr/bin/env python3
```

This ensured the script always used `/usr/bin/python3` even if uv-managed Python was in PATH.

**2. Install PyYAML for system Python on each platform**:

WSL/Debian (bootstrap script):

```bash
sudo apt install -y python3-pyyaml  # Correct package name
```

Arch Linux (`install/packages.yml`):

```yaml
- name: python3-yaml
  pacman: python-yaml
```

macOS (`install.sh` `main()`):

```bash
/usr/bin/python3 -m pip install --user PyYAML
```

On macOS this bootstrap must run **before** the platform is read from the manifest.
`manifest_field` calls `parse_packages.py`, which imports `yaml`, but Apple's bundled
`/usr/bin/python3` ships without PyYAML. The macOS package phase installs it — but that
phase runs only *after* the platform is known, so the bootstrap lives in `main()` (gated
on `detect_os`, which uses `uname` and needs no Python dependency). Without it a fresh Mac
parses an empty platform and dies with `Unsupported platform`.

**3. Use Docker with WSL rootfs for testing** (`tests/e2e/` (the `wsl` environment)):

```bash
# Download official WSL Ubuntu rootfs (one-time, cached)
curl -L https://cloud-images.ubuntu.com/wsl/noble/current/ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz

# Import into Docker (100% exact WSL environment, 563 packages)
gunzip -c ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz | docker import - wsl-ubuntu:24.04

# Run tests in authentic WSL environment
uv run pytest tests/e2e --docker -k wsl
```

This provides **100% accurate testing** - if it fails in the test, it will fail in WSL. If it passes in the test, it will pass in WSL.

**4. Verify the interpreter can import the package**
(`tests/e2e/test_machine.py::test_the_interpreter_the_installers_get_can_import_the_package`):

```python
assert machine.succeeds('"$(uv tool dir)/dotfiles/bin/python" -c "import dotfiles, yaml"')
```

Defense in depth - catches issues even if test environment differs. The property
is the same one the verification shell script asserted; the subject is now the
interpreter the CLI was installed with, which is the only one anything runs on.

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

## The bootstrap goes away on Ubuntu 26.04

Measured 2026-08-08 against `wsl-ubuntu:26.04`, imported from a real rootfs by
`tests/e2e/` (the `wsl` environment): it ships `/usr/bin/python3` at **3.14.4** and **PyYAML 6.0.3**
already installed. The premise above — that a fresh WSL install has no PyYAML — no longer holds for
that release, and the bootstrap step this learning exists to fix has nothing left to do there.

Do not read that as "the problem was imaginary". It is the same shape as the original bug, inverted:
the environment happening to carry the dependency is exactly what let the wrong package name pass
unnoticed the first time. The durable fix is the one the Python conversion makes — installing the
package with its dependencies declared, so nothing has to be true about the machine beforehand.

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
| --- | --- | --- |
| Accuracy | 100% (563 packages) | ~75% (426 packages) |
| Startup | <5 seconds | 1-2 minutes |
| Resources | Lightweight | VM overhead |
| Cleanup | Instant | 10-20 seconds |
| Use Case | Primary testing | Backup/fallback |

## Related

- `tests/e2e/` — the container installs, WSL among them
- `install/wsl/docker-images.sh` - Manage WSL Docker images
- `tests/install/README.md` - Full install-test suite (e2e, integration, unit)
- `install/wsl/` - WSL installation scripts
- `tests/e2e/test_verification.py` - Installation verification, derived from the resolver
- `docs/development/testing.md` - Testing documentation
