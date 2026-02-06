# Docker Configuration

Docker setup varies significantly across platforms due to architectural differences between macOS and Linux. This guide explains the configuration used in this dotfiles repository.

## Platform Differences

### macOS (OrbStack)

macOS cannot run containers natively and requires a Linux VM. This setup uses **OrbStack** instead of Docker Desktop.

**Container Runtime**: OrbStack (optimized lightweight VM with Docker integration)

OrbStack provides a fast, lightweight Linux VM with native Docker CLI integration. It bundles Docker CLI, Docker Compose, and container management — no separate installs needed.

**Installation**:

```bash
brew install --cask orbstack
```

**Start OrbStack**:

Open the OrbStack app. Docker is available immediately — no manual daemon start required. OrbStack runs in the menu bar and starts automatically on login.

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

- macOS: OrbStack includes docker compose built-in
- Linux: Package repos provide `docker-compose-plugin` or equivalent

## Docker Completions

Docker completions are installed automatically:

**macOS**:

- OrbStack provides Docker CLI completions automatically

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

For a terminal-based Docker management UI, this setup uses **lazydocker**.

**Installation**:

```bash
# Already included in packages.yml
go install github.com/jesseduffield/lazydocker@latest
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

Open OrbStack (runs in menu bar, starts on login by default).

**Linux**:

```bash
sudo systemctl start docker
```

### Verify Installation

```bash
docker --version
docker compose version  # V2 command
orbctl version          # macOS only
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

Docker Desktop was replaced with OrbStack + lazydocker because:

1. **Licensing**: Docker Desktop requires a paid license for commercial use
2. **Performance**: OrbStack uses less memory and CPU than Docker Desktop
3. **Simplicity**: OrbStack integrates Docker CLI seamlessly with zero configuration
4. **XDG compliance**: Docker Desktop creates files in home directory
5. **Cross-platform**: Same Docker CLI experience across macOS and Linux

## Troubleshooting

### macOS: Cannot connect to Docker daemon

Ensure OrbStack is running (check the menu bar icon):

```bash
orbctl status
```

If the Docker socket is not found, OrbStack may need to be restarted from the menu bar.

### Linux: Permission denied

Add user to docker group:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### docker compose not found

**macOS**: Restart OrbStack — docker compose is built-in.

**Linux**: Install docker-compose-plugin:

```bash
sudo apt install docker-compose-plugin  # WSL
sudo pacman -S docker-compose            # Arch
```
