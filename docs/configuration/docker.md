# Docker Configuration

Docker setup varies significantly across platforms due to architectural differences between macOS and Linux. This guide explains the configuration used in this dotfiles repository.

## Platform Differences

### macOS (Colima)

macOS cannot run containers natively and requires a Linux VM. This setup uses **Colima** instead of Docker Desktop.

**Container Runtime**: Colima (Lima-based VM running containerd)

Colima creates a lightweight Linux VM to run containers. The Docker CLI communicates with the VM to manage containers.

**Installation**:

```bash
brew install docker docker-compose colima
```

**Start Colima**:

```bash
colima start
```

**docker-compose Plugin Setup**:
The macOS installation automatically configures docker-compose as a CLI plugin via symlink:

```bash
mkdir -p "$DOCKER_CONFIG/cli-plugins"
ln -sfn $(brew --prefix)/opt/docker-compose/bin/docker-compose \
  "$DOCKER_CONFIG/cli-plugins/docker-compose"
```

This enables the modern `docker compose` command (without hyphen).

### Linux (WSL/Arch)

Linux runs containers natively without virtualization.

**Container Runtime**: Docker Engine (native)

Linux uses the Docker daemon directly without VM overhead.

**Installation (WSL)**:

```bash
sudo apt install docker.io docker-compose-plugin
```

**Installation (Arch)**:

```bash
sudo pacman -S docker docker-compose
```

**docker-compose Plugin**:
Linux package managers install docker-compose-plugin automatically with proper integration. No manual symlink needed.

## Docker Compose: V1 vs V2

**Legacy V1** (deprecated):

- Standalone Python application
- Command: `docker-compose` (with hyphen)
- Installed separately from Docker

**Modern V2** (current):

- Native Go rewrite integrated as Docker CLI plugin
- Command: `docker compose` (without hyphen)
- Installed as part of Docker or via docker-compose package

**This dotfiles setup uses V2** across all platforms:

- macOS: `brew install docker-compose` installs V2 as plugin
- Linux: Package repos provide `docker-compose-plugin` or equivalent

## Docker Completions

Docker completions are installed automatically as dependencies:

**macOS**:

- `docker-completion` is a Homebrew dependency of `docker`
- Installed automatically when you install Docker

**Linux**:

- Completions included in Docker packages
- Activated via shell completion frameworks

No separate installation needed.

## XDG Base Directory Compliance

Docker configuration is kept in `~/.config/docker` instead of `~/.docker`:

**zshrc configuration**:

```bash
export DOCKER_CONFIG="$XDG_CONFIG_HOME/docker"  # ~/.config/docker
```

This ensures:

- Clean home directory (no `~/.docker` pollution)
- Follows XDG Base Directory specification
- Plugin directory at `$DOCKER_CONFIG/cli-plugins/`

## GUI Alternative: lazydocker

Instead of Docker Desktop GUI, this setup uses **lazydocker** - a terminal UI for Docker management.

**Installation**:

```bash
# Already included in packages.yml
brew install lazydocker      # macOS
sudo apt install lazydocker  # WSL
sudo pacman -S lazydocker    # Arch
```

**Usage**:

```bash
lazydocker
```

**Features**:

- View containers, images, volumes, networks
- Real-time logs and stats
- Container lifecycle management (start, stop, remove)
- Keyboard-driven interface
- Lightweight alternative to Docker Desktop

## Quick Reference

### Start Docker

**macOS**:

```bash
colima start
```

**Linux**:

```bash
sudo systemctl start docker
```

### Verify Installation

```bash
docker --version
docker compose version  # V2 command
lazydocker --version
```

### Common Commands

```bash
# List containers
docker ps

# View logs
docker compose logs -f

# Clean up
docker system prune

# lazydocker TUI
lazydocker
```

## Why Not Docker Desktop?

Docker Desktop was removed in favor of Colima + lazydocker because:

1. **Licensing**: Docker Desktop requires license for commercial use
2. **Resource usage**: Colima is more lightweight
3. **XDG compliance**: Docker Desktop creates files in home directory
4. **Simplicity**: CLI + lazydocker provides all needed functionality
5. **Cross-platform**: Same CLI experience across macOS and Linux

## Troubleshooting

### macOS: Cannot connect to Docker daemon

Ensure Colima is running:

```bash
colima status
colima start
```

### Linux: Permission denied

Add user to docker group:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### docker-compose not found

Verify plugin installation:

```bash
# Check if plugin exists
ls $DOCKER_CONFIG/cli-plugins/

# macOS: Re-run setup
task macos:setup-docker-compose

# Linux: Install docker-compose-plugin
sudo apt install docker-compose-plugin  # WSL
sudo pacman -S docker-compose            # Arch
```
