# VM Testing

Testing dotfiles installation across platforms using virtual machines.

## Why VMs

- Clean environment every time
- Rapid iteration: destroy, fix, test again
- Test all platforms without multiple machines
- Catch installation issues early

## Testing Strategy

| Platform | Tool | Method |
|----------|------|--------|
| Ubuntu (WSL) | multipass | Fast, lightweight |
| Arch Linux | UTM/QEMU | Requires Arch ISO |
| macOS | Fresh user account | VMs too complex |

## Prerequisites

```sh
brew install --cask multipass  # Ubuntu testing
brew install --cask utm        # Arch testing
```

## Ubuntu Testing

**Basic workflow**:

```sh
# Create VM
multipass launch --name dotfiles-test

# Access VM
multipass shell dotfiles-test

# Inside VM: test installation
git clone https://github.com/yourusername/dotfiles.git
cd dotfiles
bash management/wsl-setup.sh

# Exit and destroy
exit
multipass delete dotfiles-test
multipass purge
```

**Mount local directory** (for live editing):

```sh
multipass launch --name dotfiles-test
multipass mount ~/dotfiles dotfiles-test:~/dotfiles
multipass shell dotfiles-test
```

**Automated test script**:

The repository includes `management/test-wsl-setup.sh` for automated testing:

```sh
cd ~/dotfiles
./management/test-wsl-setup.sh
```

**Features**:

- Real-time output display with simultaneous logging to `~/dotfiles/test-wsl-setup.log`
- Timing information for each step and overall execution (MM:SS format)
- Colored output with section headers and timestamps
- Comprehensive summary with VM info and next steps
- 10 CPUs, 32GB RAM allocation for faster testing

**Example output**:

```bash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1/4: Launching Multipass VM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Launched: dotfiles-wsl-test

⏱ Step 1: Launch VM completed in 02:15

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIMING SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Step 1: Launch VM          02:15
  Step 2: Clone dotfiles     00:45
  Step 3: WSL setup          12:30
  Step 4: Verification       01:05
  ─────────────────────────────────────────────
  Total time:                16:35
```

**Manual test script**:

```sh
#!/usr/bin/env bash
VM_NAME="dotfiles-test"

multipass launch --name "$VM_NAME" --cpus 2 --mem 2G
multipass exec "$VM_NAME" -- git clone https://github.com/user/dotfiles.git
multipass exec "$VM_NAME" -- bash dotfiles/management/wsl-setup.sh
multipass exec "$VM_NAME" -- bash -c "cd dotfiles && task verify"
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
