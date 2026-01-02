# Trivy & mkcert: Installation Method Analysis

**Date:** 2025-11-28
**Purpose:** Determine optimal installation method based on update frequency and package manager lag

---

## Executive Summary

### Recommendation

**trivy**: ✅ **Use GitHub Binary Installation**

- Very active development (monthly releases)
- Security scanner requires latest vulnerability databases
- Package managers lag by 0-2 versions

**mkcert**: ✅ **Use System Package Managers**

- Stable tool (last release April 2022)
- Feature-complete, no active development
- Version 1.4.4 is current everywhere

---

## Detailed Analysis

### trivy (Container/IaC Vulnerability Scanner)

#### Release Frequency (GitHub)

**Latest Release:** v0.67.2 (October 10, 2025)

**Release Pattern (Last 12 months):**

- v0.67.2 - Oct 10, 2025
- v0.67.1 - Oct 9, 2025
- v0.67.0 - Sep 30, 2025
- v0.66.0 - Sep 2, 2025
- v0.65.0 - Jul 31, 2025
- v0.64.1 - Jul 3, 2025
- v0.64.0 - Jul 1, 2025
- v0.63.0 - May 29, 2025
- v0.62.1 - May 6, 2025
- v0.62.0 - Apr 30, 2025
- v0.61.1 - Apr 18, 2025
- v0.61.0 - Mar 28, 2025
- v0.60.0 - Mar 5, 2025
- v0.59.1 - Feb 5, 2025
- v0.59.0 - Jan 30, 2025
- v0.58.2 - Jan 14, 2025
- v0.58.1 - Dec 24, 2024
- v0.58.0 - Dec 3, 2024
- v0.57.1 - Nov 18, 2024
- v0.57.0 - Nov 2, 2024

**Update Frequency:** ~1-2 releases per month (very active)

**Why Frequent Updates Matter:**

- Security vulnerability database updates
- New CVE detections
- Support for new package ecosystems
- Bug fixes for scanning accuracy

#### Package Manager Versions

| Package Manager | Version | Lag Behind Latest | Last Checked |
|----------------|---------|-------------------|--------------|
| **Arch (pacman)** | 0.67.2 | ✅ Current | Nov 2025 |
| **Homebrew** | 0.65.0 | ⚠️ 2 versions behind | Nov 2025 |
| **Debian/Ubuntu (apt)** | Via official repo | ✅ Usually current | Nov 2025 |

**APT Installation Notes:**

- Aquasecurity maintains official deb repository
- Updates pushed regularly to match releases
- Requires adding custom repository (not in default Ubuntu/Debian repos)

**Installation Methods:**

1. **APT (via Aquasecurity repo):**

   ```bash
   wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
   echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
   sudo apt-get update
   sudo apt-get install trivy
   ```

2. **Pacman (Arch):**

   ```bash
   sudo pacman -S trivy
   ```

3. **Homebrew:**

   ```bash
   brew install trivy
   ```

4. **GitHub Binary:**

   ```bash
   # Download from https://github.com/aquasecurity/trivy/releases
   # Extract and move to ~/.local/bin
   ```

#### Recommendation: **GitHub Binary Installation**

**Reasoning:**

1. **Security-Critical Tool**: As a vulnerability scanner, having the latest version is crucial for detecting new CVEs
2. **Fast Updates**: 1-2 releases per month means package managers can lag
3. **Consistent Versioning**: GitHub releases work identically across all platforms
4. **No Extra Repos**: Avoid maintaining platform-specific repository configurations

**Trade-offs:**

- Must maintain install script (already common pattern in dotfiles)
- Manual updates via install script (acceptable for development tool)
- Package managers handle dependencies automatically (trivy is self-contained, minimal deps)

---

### mkcert (Local HTTPS Certificates)

#### Release Frequency (GitHub)

**Latest Release:** v1.4.4 (April 26, 2022)

**Complete Release History:**

- v1.4.4 - Apr 26, 2022 ⭐ **Current**
- v1.4.3 - Nov 25, 2020 (18 months earlier)
- v1.4.2 - Oct 26, 2020
- v1.4.1 - Nov 9, 2019
- v1.4.0 - Aug 16, 2019
- v1.3.0 - Feb 3, 2019
- v1.2.0 - Jan 7, 2019
- v1.1.2 - Aug 25, 2018
- v1.1.1 - Aug 19, 2018
- v1.1.0 - Aug 13, 2018
- v1.0.1 - Jul 30, 2018
- v1.0.0 - Jul 7, 2018

**Update Frequency:** Stable/mature (last release 2.5+ years ago)

**Project Status:**

- Feature-complete and stable
- No active development (maintenance mode)
- Tool works perfectly for its narrow scope
- No breaking changes expected

#### Package Manager Versions

| Package Manager | Version | Lag Behind Latest | Notes |
|----------------|---------|-------------------|-------|
| **Arch (pacman)** | 1.4.4-3 | ✅ Current | Official repo |
| **Homebrew** | 1.4.4 | ✅ Current | Official formula |
| **Debian/Ubuntu (apt)** | 1.4.4 | ✅ Current | Standard repos |

**ALL PACKAGE MANAGERS ARE CURRENT** ✅

#### Recommendation: **System Package Managers**

**Reasoning:**

1. **Stable Tool**: No updates in 2.5+ years = mature, complete software
2. **Universal Availability**: All package managers have current version (1.4.4)
3. **Zero Maintenance**: Set-and-forget installation
4. **Dependency Handling**: Package managers install NSS libraries automatically
5. **Standard Practice**: mkcert is a well-established tool in all ecosystems

**Configuration:**

```yaml
- name: mkcert
  apt: mkcert
  pacman: mkcert
  brew: mkcert
  description: Local HTTPS certificates for development
```

**Post-Install Setup:**

```bash
# Run once after installation
mkcert -install
```

**Trade-offs:**

- None - package managers are ideal for this use case

---

## Installation Strategy Summary

### Use GitHub Binary Releases When

- ✅ Tool has frequent releases (>4 per year)
- ✅ Security-critical (needs latest vulnerability data)
- ✅ Package managers lag significantly (>1 version)
- ✅ Cross-platform consistency is important
- ✅ Tool is self-contained (minimal dependencies)

**Examples in dotfiles:**

- trivy (1-2 releases/month)
- neovim (needs latest features)
- lazygit (frequent updates)
- terraform tools (fast-moving ecosystem)

### Use System Package Managers When

- ✅ Tool is stable/mature (infrequent releases)
- ✅ All package managers have current version
- ✅ Tool has system dependencies (NSS, certificates, etc.)
- ✅ Feature-complete (no active development)
- ✅ Standard utility (widely available)

**Examples in dotfiles:**

- mkcert (stable since 2022)
- git (mature, universal)
- tmux (stable releases)
- jq (mature tool)

---

## Implementation Changes Required

### 1. Keep trivy as GitHub Binary

**Action:** Create `management/scripts/install-trivy.sh`

**Pattern:** Similar to install-terrascan.sh

**Binary Pattern:** `trivy_{version}_{OS}_{arch}.tar.gz`

- macOS: `trivy_{version}_macOS-64bit.tar.gz` or `trivy_{version}_macOS-ARM64.tar.gz`
- Linux: `trivy_{version}_Linux-64bit.tar.gz` or `trivy_{version}_Linux-ARM64.tar.gz`

**packages.yml entry:**

```yaml
github_binaries:
  - name: trivy
    repo: aquasecurity/trivy
    install_script: install-trivy.sh
    binary_pattern: "trivy_{version}_{OS}_{arch}.tar.gz"
    install_dir: "~/.local/bin"
    description: Container/IaC vulnerability scanner
```

### 2. Keep mkcert in System Packages

**Action:** Already done ✅

**packages.yml entry:**

```yaml
system_packages:
  - name: mkcert
    apt: mkcert
    pacman: mkcert
    brew: mkcert
    description: Local HTTPS certificates for development
```

**No install script needed** - package managers handle everything.

---

## Sources & References

### trivy

- [Trivy Installation Documentation](https://trivy.dev/docs/latest/getting-started/installation/)
- [GitHub - aquasecurity/trivy-repo](https://github.com/aquasecurity/trivy-repo)
- [Arch Linux - trivy 0.67.2-1](https://archlinux.org/packages/extra/x86_64/trivy/)
- [trivy — Homebrew Formulae](https://formulae.brew.sh/formula/trivy)
- [Install Trivy on Ubuntu 24.04](https://lindevs.com/install-trivy-on-ubuntu)

### mkcert

- [GitHub - FiloSottile/mkcert](https://github.com/FiloSottile/mkcert)
- [Arch Linux - mkcert 1.4.4-3](https://archlinux.org/packages/extra/x86_64/mkcert/)
- [mkcert — Homebrew Formulae](https://formulae.brew.sh/formula/mkcert)
- [mkcert: Create Trusted SSL Certificate for Local Development](https://www.tecmint.com/mkcert-create-ssl-certs-for-local-development/)
- [Creating Locally Trusted SSL Certificates using mkcert](https://computingforgeeks.com/create-locally-trusted-ssl-certificates-on-linux-macos-using-mkcert/)

---

## Next Steps

1. ✅ Keep mkcert in system_packages (already done)
2. ⏸️ Move trivy from system_packages to github_binaries
3. ⏸️ Create `management/scripts/install-trivy.sh`
4. ⏸️ Update packages.yml with correct trivy entry
5. ⏸️ Test trivy installation on macOS

---

## Conclusion

**trivy**: GitHub binary installation is the clear choice due to:

- Very active development (monthly releases)
- Security-critical nature (needs latest CVE data)
- Self-contained binary (no dependency concerns)

**mkcert**: System package manager installation is ideal because:

- Stable, mature tool (no updates in 2.5+ years)
- All package managers have current version
- Handles NSS dependencies automatically
- Zero maintenance required

This analysis provides a framework for future package installation decisions based on release cadence and package manager lag.
