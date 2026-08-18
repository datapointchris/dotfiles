# Docker Configuration

Each platform reaches Docker by a different route, and the differences are architectural rather
than cosmetic. This page records the choices behind those routes.

## macOS runs OrbStack, not Docker Desktop

macOS cannot run containers natively and needs a Linux VM, so the runtime is a real choice here.
WSL takes Docker Desktop because Windows offers no comparable alternative and the work machine
already has it. On macOS the choice is open, and Docker Desktop requires a paid licence for
commercial use.

OrbStack bundles the Docker CLI, Compose, Buildx and shell completions. Do not install Homebrew's
`docker`, `docker-completion`, `docker-buildx` or `docker-compose` formulas alongside it. They
create version conflicts and fragile symlinks over binaries OrbStack already provides. Kubernetes
tooling is a separate Homebrew concern, declared in `install/packages.yml` so Arch gets it too.

OrbStack installs its binaries at `/Applications/OrbStack.app/Contents/MacOS/xbin/`. `docker
compose` and `docker buildx` resolve as CLI plugins only once the Docker config names that
directory in `cliPluginsExtraDirs`. That is the `orbstack-docker-plugins` row of
`install/system.yml`, so `dotfiles plan` reports it when it is missing and `dotfiles apply` merges
it into whatever else the config holds. `resolve.Stage` orders the work, and it puts
`SYSTEM_CONFIG` after `SYSTEM_APPS`, so the row converges after the OrbStack cask installs. A
plugin directory that does not exist yet is nothing to point at.

## Arch talks to the daemon directly

Linux runs containers natively, so there is no VM and nothing to choose. Socket access without
sudo comes from the `docker` group membership declared in `install/system.yml` and converged by
`dotfiles system apply`. Never add the group with `usermod` by hand — the declaration is what
makes the membership survive a rebuild.

## WSL borrows the Windows engine

WSL does not run its own Docker Engine. The distro borrows the CLI and daemon from Docker Desktop
on the Windows side. Two engines competing for one distro is the thing being avoided: Docker
Desktop already runs one in its own utility VM and shares it across every enabled distro. Every
Docker entry in `install/packages.yml` therefore declares `excludes_host: wsl`, and
`install/wsl/docker-repo.sh` exits early when it detects WSL.

The exclusion has to be a declaration. Filtering the packages out with a `grep -v` in the WSL
package script keeps them off the machine while leaving them declared, so `check` reports them
missing forever.

Enable the integration in **Docker Desktop → Settings → Resources → WSL Integration**, toggle the
Ubuntu distro, then Apply & Restart. The CLI appears at
`/mnt/wsl/docker-desktop/cli-tools/usr/bin/` and goes on the distro's `PATH`.

Until that toggle is on, Ubuntu's own `/usr/bin/docker` stub answers instead. It exists only to
print the "could not be found in this WSL 2 distro" hint, and it exits 1 for every subcommand —
including `docker completion zsh`. That is why `cache_eval` in `.zshrc` records a failure marker
for it rather than retrying the generator in every shell. Enabling the integration changes what
`docker` resolves to, the marker stops matching, and completion regenerates on the next shell.

### The native engine inside WSL is a deliberate departure

Docker Desktop's licence is per-seat for commercial use, so a work machine may not have it. The
alternative is a native engine inside the distro: run `install/wsl/docker-repo.sh` past its WSL
guard, install `docker-ce` and the plugins by hand, and enable systemd so `systemctl start docker`
works.

```ini
# /etc/wsl.conf
[boot]
systemd = true
```

Systemd takes effect after `wsl --shutdown` from Windows and needs WSL 0.67.6 or newer. Nothing in
the installer supports this path.

## Completions are generated from the CLI

`.zshrc` generates the zsh completion with `docker completion zsh` and caches it under
`$XDG_CACHE_HOME/zsh/completions`. Neither Homebrew nor OrbStack installs a `_docker` on fpath, and
the compose plugin ships no completion of its own. The generated one covers `docker compose` as
well. Where a package does supply `_docker`, the generated copy wins, because it is sourced after
compinit and re-registers the command.

## Config lives under XDG

`.zshrc` exports `DOCKER_CONFIG="$XDG_CONFIG_HOME/docker"`, which also moves the plugin directory
to `$DOCKER_CONFIG/cli-plugins/`.
