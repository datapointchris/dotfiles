# Installation Testing

Testing dotfiles installation across platforms using containers and virtual machines.

## Why Test in Isolated Environments

- Clean environment every time
- Rapid iteration: destroy, fix, test again
- Test all platforms without multiple machines
- Catch installation issues early
- Match production environment exactly

## Testing Strategy

| Platform | Method | Tool | Accuracy |
|----------|--------|------|----------|
| Ubuntu (WSL) | Docker | Official WSL rootfs | 100% exact match |
| Arch Linux | Docker | Official Arch base image | 100% exact match |
| macOS | Fresh user account | Local testing | Full |

## Prerequisites

```sh
# Docker Desktop (required)
brew install --cask docker
```

## Testing with Docker (Recommended)

### Unified Test Dispatcher

The `management/test-install.sh` script provides a unified interface for testing across all platforms:

```sh
cd ~/dotfiles

# Test specific platform
bash management/test-install.sh -p wsl        # WSL Ubuntu (Docker)
bash management/test-install.sh -p arch       # Arch Linux (Docker)
bash management/test-install.sh -p macos      # macOS (local user)

# Keep container after test for debugging
bash management/test-install.sh -p wsl -k
bash management/test-install.sh -p arch -k

# Show help
bash management/test-install.sh --help
```

### Run and Summarize (Context-Friendly Testing)

For long-running tests, use `run-and-summarize.sh` to avoid context overload when working with Claude Code:

```sh
# Run test with periodic updates every 30 seconds
bash management/run-and-summarize.sh "bash management/test-install.sh -p arch --keep" test-arch.log 30

# What this does:
# - Runs test in background
# - Shows progress every 30 seconds
# - Shows last 5 lines every 5 checks
# - Generates concise summary when complete
# - Saves full logs to test-arch.log

# Why use this:
# - Prevents flooding context with verbose installation output
# - Get periodic updates without full log streaming
# - Claude receives only summary, not thousands of log lines
```

The summarize script (`management/summarize-log.sh`) creates `.summary` files with:

- File size and line count
- Success/failure counts
- Final result status
- Last 20 lines of output (most important context)

This is especially useful for CI/CD integration or when repeatedly testing installations.

Scripts are located in `management/` directory alongside other testing tools.

### Platform-Specific Test Scripts

Located in `management/testing/`:

- `test-wsl-install-docker.sh` - WSL Ubuntu testing with Docker
- `test-arch-install-docker.sh` - Arch Linux testing with Docker
- `test-macos-install-user.sh` - macOS testing with fresh user account
- `test-install-helpers.sh` - Shared utilities for formatting and timing

### Why Docker for Testing

Docker provides **100% exact match** to real environments:

**WSL Ubuntu**:

- 563 pre-installed packages (same as WSL Ubuntu 24.04)
- Official Microsoft/Canonical WSL distribution
- Fast container startup (~seconds vs minutes for VMs)

**Arch Linux**:

- Official Arch Linux base image
- Latest rolling release packages
- Realistic Arch environment
- Automatic library linking fixes (pcre2 for git)
- Binary naming differences (7z vs 7zz) handled automatically

**Advantages**:

- Lightweight resource usage
- Fast iteration (destroy, fix, test again)
- No guessing about environment differences
- Automated cleanup (or keep with `-k` flag)

### Test Phases

Docker test scripts run 7 comprehensive phases:

1. **Prepare Docker Image** - Pull/update official platform image
2. **Start Container** - Launch container with dotfiles mounted
3. **Prepare Environment** - Create test user and copy dotfiles
4. **Run Installation** - Execute `install.sh` script
5. **Verify Installation** - Run `verify-installation.sh` checks
6. **Detect Alternates** - Run `detect-alternate-installations.sh`
7. **Test Updates** - Run platform-specific `update-all` task

### Features

- Real-time output with logging (`test-{platform}-docker.log`)
- Timing for each step (MM:SS format)
- Colored output with section headers
- Automatic cleanup (or keep with `-k` flag)
- Comprehensive verification and duplicate detection

### Test Logs

Each test run creates a detailed log file:

- WSL: `test-wsl-docker.log`
- Arch: `test-arch-docker.log`
- macOS: `test-macos.log`

Logs include all installation output, timing information, and test results.

## Alternative Testing

Docker is the recommended approach. For environments without Docker, VMs or cloud instances can be used but require more setup time and resources.

## macOS Testing

**Use separate user account**:

1. Create new standard user in System Preferences
2. Log in as that user
3. Install and test dotfiles
4. Delete user when done

macOS VMs are too complex and resource-intensive. Fresh user accounts provide clean testing environment.

## Verification

The test scripts automatically run comprehensive verification using `management/verify-installation.sh`. This checks:

- Core build tools (git, curl, wget, make)
- Task runner installation
- Shell and terminal tools (zsh, tmux, bat, fd, fzf, ripgrep, zoxide, eza)
- Development tools (neovim, lazygit, yazi, glow, duf)
- Version managers (nvm, uv, cargo-binstall)
- Language servers and Go tools
- Platform-specific tools

The verification script validates that tools are installed in the expected locations (e.g., `~/.local/bin/`, `~/.cargo/bin/`) and reports any duplicate installations.

### Manual Verification

If testing manually without the automated scripts:

```sh
# Run comprehensive verification
cd ~/dotfiles
bash management/verify-installation.sh

# Check for duplicate installations
bash management/detect-alternate-installations.sh
```

## Iteration Workflow

1. **Test** in clean VM
2. **Capture errors** (screenshot, save output)
3. **Fix** bootstrap/taskfile scripts
4. **Destroy** VM
5. **Repeat** until flawless

Document quirks discovered in [Platform Differences](../reference/platforms.md).
