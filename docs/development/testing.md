# Installation Testing

Testing dotfiles installation across platforms using containers and virtual machines.

## Why Test in Isolated Environments

- Clean environment every time
- Rapid iteration: destroy, fix, test again
- Test all platforms without multiple machines
- Catch installation issues early
- Match production environment exactly

## Testing Strategy

| Platform | Primary Tool | Method | Accuracy |
|----------|-------------|--------|----------|
| Ubuntu (WSL) | **Docker** | Official WSL rootfs | 100% exact match |
| Ubuntu (WSL) | Multipass | Cloud images | ~75% (backup method) |
| Arch Linux | UTM/QEMU | ISO installation | Full |
| macOS | Fresh user account | Local testing | Full |

## Prerequisites

```sh
# Docker Desktop (required for WSL testing)
brew install --cask docker

# Multipass (optional, backup WSL testing)
brew install --cask multipass

# UTM (optional, Arch testing)
brew install --cask utm
```

## WSL Ubuntu Testing (Docker - Recommended)

### Why Docker for WSL Testing

Docker with official WSL rootfs provides **100% exact match** to actual WSL Ubuntu installations:

- **563 pre-installed packages** (same as WSL Ubuntu 24.04)
- Official Microsoft/Canonical WSL distribution
- Fast container startup (~seconds vs minutes for VMs)
- Lightweight resource usage
- No guessing about environment differences

### Automated Test Script

Run the comprehensive Docker-based test:

```sh
cd ~/dotfiles
./management/test-wsl-docker.sh
```

**Options**:

```sh
./management/test-wsl-docker.sh              # Test Ubuntu 24.04 (default)
./management/test-wsl-docker.sh -v 22.04     # Test Ubuntu 22.04
./management/test-wsl-docker.sh -k           # Keep container for debugging
```

**First Run**: Downloads official WSL rootfs (~340MB, cached for future tests)

### Test Phases

The Docker test script runs 6 comprehensive phases:

1. **Prepare Docker Image** - Download and import WSL rootfs (one-time, cached)
2. **Start Container** - Launch container with dotfiles mounted
3. **Prepare Environment** - Configure test environment
4. **Run Installation** - Execute `install.sh` script
5. **Verify Installation** - Run comprehensive verification checks
6. **Test Updates** - Run `task wsl:update-all`

### Features

- Real-time output with logging to `test-wsl-docker.log`
- Timing for each step (MM:SS format)
- Colored output with section headers
- Automatic cleanup (or keep with `-k` flag)
- Tests with exact WSL environment (563 packages)

### Managing Docker Images

Use the helper script to manage WSL Docker images:

```sh
# List available WSL images
./management/wsl-docker-images.sh list

# Build/rebuild an image
./management/wsl-docker-images.sh build 24.04

# Show cache and image info
./management/wsl-docker-images.sh info

# Remove image
./management/wsl-docker-images.sh remove 24.04

# Clean cached rootfs files
./management/wsl-docker-images.sh clean

# Remove everything (images + cache)
./management/wsl-docker-images.sh clean-all
```

### Manual Docker Testing

For custom testing scenarios:

```sh
# Build image (if not exists)
./management/wsl-docker-images.sh build 24.04

# Run container with dotfiles mounted
docker run -it --rm \
  --mount type=bind,source="$PWD",target=/dotfiles,readonly \
  wsl-ubuntu:24.04 bash

# Inside container: copy dotfiles and test
cp -r /dotfiles /root/dotfiles
cd /root/dotfiles
bash install.sh
```

## WSL Ubuntu Testing (Multipass - Alternative)

Multipass uses Ubuntu cloud images (~426 packages) which differ from WSL (563 packages). Use Docker for accurate testing, but Multipass works as a backup method.

### Automated Test Script

```sh
cd ~/dotfiles
./management/test-install.sh
```

### Manual Multipass Testing

```sh
# Create VM
multipass launch --name dotfiles-test

# Access VM
multipass shell dotfiles-test

# Inside VM: test installation
git clone https://github.com/yourusername/dotfiles.git
cd dotfiles
bash install.sh

# Exit and destroy
exit
multipass delete dotfiles-test
multipass purge
```

## Arch Linux Testing

**Using UTM**:

1. Download Arch ISO: <https://archlinux.org/download/>
2. Create new VM in UTM with ISO
3. Boot, install base system
4. Test dotfiles installation

**Using QEMU**:

```sh
# Create disk
qemu-img create -f qcow2 arch-test.qcow2 20G

# Boot installer
qemu-system-x86_64 -cdrom archlinux-x86_64.iso \
  -boot order=d -drive file=arch-test.qcow2,format=qcow2 \
  -m 2G -enable-kvm
```

## macOS Testing

**Use separate user account**:

1. Create new standard user in System Preferences
2. Log in as that user
3. Install and test dotfiles
4. Delete user when done

macOS VMs are too complex and resource-intensive. Fresh user accounts provide clean testing environment.

## Verification Checklist

After installation in VM:

```sh
# Check installations
task --version
toolbox list
theme-sync current

# Check tools work
bat --version
eza --version
rg --version

# Check shell
echo $SHELL  # Should be /bin/zsh
echo $PATH | grep ".local/bin"

# Check Neovim
nvim --version  # Should be 0.11+
```

## Common Issues

**VM network slow**: Use wired connection, check corporate proxy settings

**Multipass won't start**: Check hypervisor enabled, restart multipass service

**UTM low performance**: Allocate more RAM/CPU, enable hardware acceleration

## Iteration Workflow

1. **Test** in clean VM
2. **Capture errors** (screenshot, save output)
3. **Fix** bootstrap/taskfile scripts
4. **Destroy** VM
5. **Repeat** until flawless

Document quirks discovered in [Platform Differences](../reference/platforms.md).
