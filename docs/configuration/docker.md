# Docker Configuration

Docker setup varies significantly across platforms due to architectural differences between macOS and Linux. This guide explains the configuration used in this dotfiles repository.

## Platform Differences

### macOS (OrbStack)

macOS cannot run containers natively and requires a Linux VM. This setup uses **OrbStack** instead of Docker Desktop.

**Container Runtime**: OrbStack (optimized lightweight VM with Docker integration)

OrbStack provides a fast, lightweight Linux VM with native Docker CLI integration. It bundles Docker CLI, Docker Compose, Docker Buildx, and shell completions — no Homebrew docker packages needed. (Kubernetes tooling — `kubectl`, `helm`, `k9s`, etc. — is installed via Homebrew separately so it's also available on Arch; see `install/packages.yml`.)

**Installation**:

```bash
brew install --cask orbstack
```

**Plugin Discovery**: OrbStack installs its binaries at `/Applications/OrbStack.app/Contents/MacOS/xbin/`. To make `docker compose` and `docker buildx` work as CLI plugins, the Docker config needs `cliPluginsExtraDirs` pointing to that directory. This is the `orbstack-docker-plugins` row of `install/system.yml`, so `dotfiles plan` reports it when it is missing and `dotfiles apply` merges it into whatever else the config holds. It runs after the OrbStack cask, because a plugin directory that does not exist is nothing to point at.

**Start OrbStack**:

Open the OrbStack app. Docker is available immediately — no manual daemon start required. OrbStack runs in the menu bar and starts automatically on login.

### Arch

Linux runs containers natively without virtualization, so Arch talks to the Docker daemon directly with no VM overhead.

**Container Runtime**: Docker Engine (native)

**Installation**:

```bash
sudo pacman -S docker docker-compose
```

The `docker-compose-plugin` equivalent comes from the package manager with the plugin path already wired up — no manual symlink needed.

### WSL (Docker Desktop integration)

WSL does **not** run its own Docker Engine. The distro borrows the CLI and daemon from Docker Desktop on the Windows side, which is why every Docker entry in `packages.yml` declares `excludes_host: wsl` and `install/wsl/docker-repo.sh` exits early when it detects WSL. Two engines competing for one distro is the thing being avoided; Docker Desktop already runs one in its own utility VM and shares it across every enabled distro. The exclusion used to be a `grep -v` in the WSL package script, which kept them out of the install and left `check` reporting all five missing forever.

Enable it in **Docker Desktop → Settings → Resources → WSL Integration**, toggle the Ubuntu distro, then Apply & Restart. The CLI appears at `/mnt/wsl/docker-desktop/cli-tools/usr/bin/` and is put on `PATH` for the distro.

Until that toggle is on, Ubuntu's own `/usr/bin/docker` stub answers instead. It exists only to print the "could not be found in this WSL 2 distro" hint and exits 1 for every subcommand, including `docker completion zsh` — which is why `cache_eval` in `.zshrc` records a failure marker for it rather than retrying the generator in every shell. Enabling the integration changes what `docker` resolves to, the marker no longer matches, and completion regenerates on the next shell.

Where Docker Desktop is not an option — its license is per-seat for commercial use, so a work machine may not have it — the alternative is a native engine inside the distro: run `install/wsl/docker-repo.sh` past its WSL guard, install `docker-ce` and the plugins by hand, and enable systemd so `systemctl start docker` works. That is a deliberate departure from the setup above, not a supported path through the installer.

```ini
# /etc/wsl.conf
[boot]
systemd = true
```

Systemd takes effect after `wsl --shutdown` from Windows and needs WSL 0.67.6 or newer.

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

- macOS: OrbStack provides compose via `cliPluginsExtraDirs` in Docker config
- Linux: Package repos provide `docker-compose-plugin` or equivalent

## Docker Completions

`.zshrc` generates the zsh completion from the CLI itself with `docker completion zsh` and caches it under `$XDG_CACHE_HOME/zsh/completions`. Neither Homebrew nor OrbStack installs a `_docker` on fpath, and the compose plugin ships no completion of its own — the generated one covers `docker compose` as well. Where a package does supply `_docker`, the generated copy wins anyway, since it is sourced after compinit and re-registers the command.

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

**Important**: Do not install Homebrew's `docker`, `docker-completion`, `docker-buildx`, or `docker-compose` formulas on macOS — OrbStack provides all of these. Installing them creates version conflicts and fragile symlinks.

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

**Arch**:

```bash
sudo systemctl start docker
```

**WSL**:

Start Docker Desktop on Windows. The daemon is shared with the distro through the WSL integration; there is no service to start inside Ubuntu.

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

## Why Not Docker Desktop? (macOS)

This applies to macOS, where a VM is unavoidable and the choice is open. WSL takes Docker Desktop because Windows offers no comparable alternative and the work machine already has it.

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

**macOS**: Ensure `cliPluginsExtraDirs` is set in `~/.config/docker/config.json`:

```json
{
  "cliPluginsExtraDirs": [
    "/Applications/OrbStack.app/Contents/MacOS/xbin"
  ]
}
```

If missing, `dotfiles system apply` writes it.

**Arch**: Install docker-compose-plugin:

```bash
sudo pacman -S docker-compose
```

**WSL**: The plugin comes from Docker Desktop along with the CLI. If `docker compose` is missing, the WSL integration is off — see the WSL section above.
