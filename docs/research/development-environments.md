# Development Environments: A Comprehensive Comparison

Modern development encompasses multiple approaches to managing development environments, each with distinct architectures, use cases, and trade-offs. This guide provides both technical depth and practical guidance for choosing and implementing development environment strategies, with a focus on dotfiles integration and real-world workflows.

## Introduction

### The "Works on My Machine" Problem

Software development has long struggled with environment inconsistency. Code that runs perfectly on one developer's machine fails mysteriously on another's, or worse, in production. Differences in OS versions, installed dependencies, environment variables, and system configurations create friction, slow onboarding, and cause production incidents.

The evolution of development environments reflects ongoing efforts to solve this problem through different approaches: virtual machines for complete isolation, containers for lightweight packaging, managed VMs like WSL2 for hybrid performance, and declarative tools like Nix for reproducibility.

### Scope and Audience

This document compares six major approaches to development environments:

1. **Dev Containers** - Docker-based development with standardized configuration
2. **WSL2** - Windows Subsystem for Linux (managed virtualization)
3. **Traditional VMs** - Full virtual machines (VirtualBox, VMware, Hyper-V)
4. **Docker Containers** - Raw Docker without devcontainer abstraction
5. **Remote Development** - Cloud-based environments (Codespaces, Gitpod)
6. **Nix-based Environments** - Declarative, reproducible development with Nix + direnv

The guide addresses developers working across multiple platforms (macOS, Linux, Windows) and scenarios (personal development, team projects, restricted corporate environments).

## Core Technologies: Technical Deep Dive

### Dev Containers

#### What They Are

Dev Containers (Development Containers) represent an **open specification** for configuring container-based development environments. Originally created by Microsoft for Visual Studio Code, the specification moved to an open standard managed by the [Development Containers Specification](https://containers.dev/) organization.

A dev container consists of:

- **`.devcontainer/devcontainer.json`** - Configuration file defining the environment
- **Docker container** - The actual runtime environment (based on Dockerfile or image)
- **Tool integration** - Editor/IDE extensions and settings synchronized into the container
- **Lifecycle hooks** - Scripts for initialization, post-creation, and post-start operations

#### Architecture and How They Work

Dev containers layer **developer experience** on top of Docker containers:

```bash
┌─────────────────────────────────────┐
│   Editor/IDE (VSCode, Cursor, etc)  │
│   - Extensions installed in container│
│   - Terminal runs in container      │
│   - LSPs run in container            │
└──────────────┬──────────────────────┘
               │ Dev Container Protocol
┌──────────────▼──────────────────────┐
│   Docker Container                   │
│   - Development tools installed      │
│   - Project dependencies             │
│   - Personal dotfiles (optional)     │
│   - User environment customization   │
└─────────────────────────────────────┘
```

**Process flow**:

1. Read `.devcontainer/devcontainer.json` configuration
2. Build or pull the specified Docker image
3. Create container with volume mounts (project directory, dotfiles)
4. Install editor/IDE extensions inside the container
5. Run `onCreateCommand`, `updateContentCommand`, `postCreateCommand` scripts
6. Connect editor interface to container runtime

#### Portability Beyond VSCode

As of 2025, dev containers are **no longer VSCode-specific**. The specification is supported by:

- **VSCode and VSCode forks** (Cursor, Windsurf) via Dev Containers extension
- **JetBrains IDEs** (IntelliJ IDEA, PyCharm, WebStorm) via native support
- **CLI tools** - Official `devcontainer` CLI for terminal-based workflows
- **DevPod** - Editor-agnostic tool that treats devcontainers as SSH-accessible remote machines
- **GitHub Codespaces** - Cloud service built on devcontainer specification
- **GitLab** - Workspaces using devcontainer configuration

The **[devcontainer CLI](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli)** enables non-VSCode workflows:

```bash
# Build and run a devcontainer
devcontainer up --workspace-folder .

# Execute commands in the container
devcontainer exec --workspace-folder . npm test

# Use with SSH for any editor
devcontainer up --workspace-folder .
ssh -p <port> vscode@localhost  # Connect with any editor that supports SSH
```

**[DevPod](https://devpod.sh/)** (November 2025) represents a significant development: it runs devcontainers as SSH-accessible machines, eliminating editor lock-in. Connect with your preferred terminal, Neovim, Emacs, or any SSH-compatible editor.

#### Dotfiles Integration

Dev containers support dotfiles through configuration in editor settings or `devcontainer.json`:

**VSCode settings approach** (`settings.json`):

```json
{
  "dotfiles.repository": "https://github.com/username/dotfiles",
  "dotfiles.targetPath": "~/dotfiles",
  "dotfiles.installCommand": "~/dotfiles/install.sh"
}
```

**devcontainer.json approach**:

```json
{
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
  "postCreateCommand": "git clone https://github.com/username/dotfiles ~/dotfiles && ~/dotfiles/install.sh"
}
```

Dotfiles are cloned and installed automatically when the container is created, allowing personal shell configurations, aliases, and tools while maintaining project-level consistency.

#### Production Readiness (2025)

Open source projects increasingly include `.devcontainer` configurations: NestJS, Supabase, Vite, and many others. This trend indicates dev containers are becoming **standard practice** for team development in 2025.

---

### WSL2 (Windows Subsystem for Linux)

#### Architecture: Managed VM vs Traditional VM

WSL2 uses a **lightweight utility virtual machine** with a real Linux kernel, but it is fundamentally different from traditional VMs:

| Aspect | WSL2 | Traditional VM |
|--------|------|----------------|
| **Kernel** | Real Linux kernel | Full guest OS kernel |
| **Boot time** | Near-instant (seconds) | Minutes |
| **Resource allocation** | Dynamic, shared with Windows | Fixed allocation (CPU, RAM) |
| **Filesystem** | Integrated with Windows (\\wsl$\) | Isolated virtual disk |
| **Networking** | Shared Windows network stack | Virtual network adapter |
| **Memory** | Returns unused memory to Windows | Reserves fixed memory |

**Technical implementation**: WSL2 runs a managed VM using Hyper-V virtualization, but abstracts away the VM management. You interact with Linux distributions as if they're native processes, while they run inside a single shared VM.

```text
┌────────────────── Windows Host ──────────────────┐
│                                                   │
│  ┌──────────────────────────────────────────┐   │
│  │  Managed Utility VM (Hyper-V)            │   │
│  │                                           │   │
│  │  ┌────────────┐  ┌────────────┐         │   │
│  │  │  Ubuntu    │  │  Debian    │  ...    │   │
│  │  │  Distro    │  │  Distro    │         │   │
│  │  └────────────┘  └────────────┘         │   │
│  │                                           │   │
│  │  Linux Kernel (shared across distros)    │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  Docker Desktop                                  │
│  ├─ Runs inside WSL2                            │
│  └─ Containers share Linux kernel                │
└───────────────────────────────────────────────────┘
```

#### Performance Characteristics

WSL2 provides **near-native Linux performance** for most operations:

- **File I/O within Linux filesystem** - Native ext4 performance
- **File I/O across Windows boundary** (accessing /mnt/c) - Slower due to translation layer
- **Network performance** - Comparable to native Linux
- **CPU-bound tasks** - Near-native speed

**Best practices for performance**:

- Store project files in Linux filesystem (`~/projects/`) not Windows (`/mnt/c/`)
- Use Git from within WSL2, not Windows Git
- Run Docker/container workloads inside WSL2

#### Relationship to Docker

Docker Desktop on Windows runs Docker **inside WSL2**, not as a separate VM:

- Docker daemon runs in the WSL2 VM
- Containers share the Linux kernel with WSL2 distros
- This eliminates the "Docker Desktop is slow" issue from WSL1/Hyper-V days

You can install Docker directly in a WSL2 distribution without Docker Desktop, using native Docker packages.

#### Dotfiles Deployment

WSL2 provides a **native Linux environment**, so dotfiles work exactly as they would on macOS or Linux:

- Clone dotfiles repository: `git clone https://github.com/username/dotfiles ~/dotfiles`
- Run installation script: `~/dotfiles/install.sh`
- Symlink configurations to `~/.config`, `~/.zshrc`, etc.

No special considerations needed - WSL2 is real Linux.

---

### Traditional Virtual Machines

#### Architecture and Isolation

Traditional VMs (VirtualBox, VMware Workstation, Hyper-V, Parallels) provide **complete hardware virtualization**:

```text
┌──────────────── Host Operating System ────────────────┐
│                                                        │
│  Hypervisor (Type 2: VirtualBox, VMware)             │
│                                                        │
│  ┌────────────────────────────────────────────────┐  │
│  │  Virtual Machine 1                             │  │
│  │                                                 │  │
│  │  ┌──────────────────────────────────────────┐ │  │
│  │  │  Guest OS (Ubuntu, Fedora, etc.)         │ │  │
│  │  │  - Full kernel                            │ │  │
│  │  │  - Complete OS stack                      │ │  │
│  │  │  - Isolated network, storage              │ │  │
│  │  └──────────────────────────────────────────┘ │  │
│  │                                                 │  │
│  │  Virtual Hardware (CPU, RAM, Disk, Network)    │  │
│  └────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

**Isolation levels**:

- **Strongest isolation** - Guest OS is completely separated from host
- **Dedicated resources** - Fixed CPU cores, RAM allocation
- **Full OS control** - Kernel modules, system configuration, init system
- **Security** - Compromise of guest doesn't affect host

#### When to Use VMs vs Containers/WSL

**Choose VMs for**:

- **Testing different operating systems** - Run Windows, various Linux distros, BSD simultaneously
- **Kernel development** - Need full control over kernel modules and configuration
- **Security research** - Strong isolation for malware analysis, exploit development
- **GPU passthrough** - Dedicate GPU to VM for AI/ML workloads
- **Desktop environment testing** - Full GNOME, KDE, or other desktop environments

**Avoid VMs for**:

- **Daily development** on modern hardware - WSL2 or native is faster
- **Quick project environments** - Containers start in seconds, VMs take minutes
- **Resource-constrained systems** - VMs require significant RAM, CPU overhead

#### Resource Implications

Traditional VMs have significant overhead:

- **RAM**: Dedicated allocation (e.g., 8GB reserved even if using 2GB)
- **CPU**: 1-2 cores typically allocated, not available to host
- **Disk**: Virtual disk file (10-40GB+) even if mostly empty
- **Boot time**: 1-5 minutes for full OS initialization

#### Dotfiles Deployment

VMs run full operating systems, so dotfiles work identically to bare metal installations:

```bash
# Inside the VM
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh
```

**Sharing dotfiles across VM instances**:

- **Snapshot base VM** - Create VM template with dotfiles installed
- **Shared folder** - Mount host directory, symlink dotfiles from there
- **Configuration management** - Use Ansible, Chef, or scripts to provision VMs

---

### Docker Containers (Without Dev Container Abstraction)

#### Raw Docker for Development

Using Docker directly (without the devcontainer specification) means manually running containers and configuring the development environment:

```bash
# Run a development container
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  -p 3000:3000 \
  node:20 \
  bash

# Inside container
npm install
npm run dev
```

#### Differences from Dev Containers

| Aspect | Raw Docker | Dev Containers |
|--------|-----------|----------------|
| **Configuration** | Dockerfile or docker-compose.yml | devcontainer.json (declarative) |
| **Editor integration** | Manual SSH or volume mounts | Automatic IDE connection |
| **Extensions** | Not managed | Automatically installed |
| **Lifecycle hooks** | Manual scripts | `onCreateCommand`, `postCreateCommand` |
| **User experience** | Command-line focused | Seamless IDE integration |
| **Dotfiles** | Manual cloning and setup | Automatic integration |

#### When Raw Docker is Appropriate

**Use raw Docker for**:

- **Production-like testing** - Run exact production container configuration
- **CI/CD pipelines** - Automated testing in containers
- **Multi-service development** - Docker Compose for complex stacks
- **Editor-agnostic workflows** - Terminal-based development

**Use dev containers for**:

- **Team standardization** - Consistent IDE setup across developers
- **Onboarding** - New developers get working environment immediately
- **Complex tooling** - Language servers, debuggers, extensions in container

---

### Remote Development Environments

#### GitHub Codespaces

**Architecture**: Cloud-hosted VMs running dev containers, integrated with GitHub.

**Key features**:

- **Instant environments** - Spin up dev container from any GitHub repo
- **Prebuilds** - Pre-build containers when commits are pushed
- **Powerful hardware** - Up to 32-core, 64GB RAM machines
- **VSCode in browser or desktop** - Full VSCode experience remotely
- **GitHub integration** - Seamless with repos, PRs, Actions

**Limitations**:

- **GitHub-centric** - Limited integration with GitLab, Bitbucket
- **Limited regions** - US West, US East, Europe West, Southeast Asia
- **Pricing** - $0.18/hour for 4-core (free: 120 hours/month + 15GB storage)

**Dotfiles integration**:

Codespaces automatically clones dotfiles from your configured repository:

```json
// GitHub Codespaces settings
{
  "dotfiles.repository": "username/dotfiles",
  "dotfiles.installCommand": "install.sh"
}
```

#### Gitpod

**Architecture**: Cloud-based ephemeral development environments with editor flexibility.

**Key features**:

- **Multi-editor support** - VSCode, JetBrains IDEs, Cursor, Windsurf, Zed (via SSH)
- **Multi-platform** - GitHub, GitLab, Bitbucket integration
- **Prebuilds** - Automated environment preparation
- **Ephemeral workspaces** - Fresh environment per task/branch
- **Affordable** - Starts at $9/month (more budget-friendly than Codespaces)

**Limitations**:

- **No GPU support** - Not suitable for AI/ML workloads
- **Self-hosting discontinued** - Previously offered, now cloud-only (Ona platform)

**Dotfiles integration**:

```yaml
# .gitpod.yml
tasks:
  - name: Setup dotfiles
    command: |
      git clone https://github.com/username/dotfiles ~/dotfiles
      ~/dotfiles/install.sh
```

#### DevPod (Local and Remote)

**DevPod** is an open-source, client-side tool that works with dev containers but offers more flexibility:

- **Editor-agnostic** - SSH-based access to devcontainers
- **Multiple providers** - Local Docker, AWS, GCP, Azure, DigitalOcean, Kubernetes
- **No vendor lock-in** - Self-hosted or cloud, your choice
- **Terminal workflows** - Use any SSH-compatible editor (Neovim, Emacs)

```bash
# DevPod workflow
devpod up github.com/user/repo
devpod ssh repo  # SSH into the devcontainer
```

#### Comparison: Codespaces vs Gitpod vs DevPod

| Feature | GitHub Codespaces | Gitpod | DevPod |
|---------|-------------------|--------|--------|
| **Cost** | $0.18/hr (4-core) | $9/mo (50hrs) | Free (self-hosted) |
| **Editor support** | VSCode | VSCode, JetBrains, SSH | Any (SSH-based) |
| **GitHub integration** | Native | Good | Manual |
| **GitLab/Bitbucket** | Limited | Native | Manual |
| **GPU support** | Yes | No | Provider-dependent |
| **Self-hosting** | No | No (discontinued) | Yes |
| **Prebuilds** | Yes | Yes | No |

---

### Nix-based Environments

#### Nix Philosophy: Declarative Reproducibility

Nix takes a fundamentally different approach than containers - **declarative package management with reproducible builds**. Instead of packaging an entire filesystem, Nix precisely specifies dependencies at the package level.

#### Nix + direnv: Automatic Environment Loading

The combination of **Nix shells** and **direnv** provides automatic, per-project environments:

```text
┌─────────────────────────────────────────────┐
│  Project Directory                          │
│                                             │
│  .envrc  ───────────────────────────────┐  │
│    use flake                             │  │
│                                          │  │
│  flake.nix ───────────┐                 │  │
│    devShells.default  │                 │  │
│      packages:        │                 │  │
│        - nodejs       │                 │  │
│        - python311    │                 │  │
│        - postgresql   │                 │  │
└──────────────────────┼──────────────────┼──┘
                       │                  │
                       ▼                  ▼
                  Nix Store          direnv
              (immutable)         (auto-load)
```

**How it works**:

1. `cd` into project directory
2. `direnv` detects `.envrc`, reads `use flake`
3. Nix evaluates `flake.nix`, builds packages (if not cached)
4. Packages are added to `$PATH` automatically
5. `cd` out of directory → packages unloaded
6. `cd` back in → instantly restored (no rebuild)

#### Example: Nix Flake for Development

```nix
# flake.nix
{
  description = "Development environment for my project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_20
            python311
            postgresql_15
            redis
          ];

          shellHook = ''
            echo "Dev environment loaded!"
            export DATABASE_URL="postgresql://localhost/mydb"
          '';
        };
      });
}
```

```bash
# .envrc
use flake
```

```bash
# Usage
cd my-project      # Automatically loads Node.js, Python, PostgreSQL
which node         # /nix/store/abc123.../bin/node
cd ..              # Unloads environment
which node         # not found (or global version)
```

#### Alternative Tools: Devenv and Devbox

Both are built on Nix but provide simpler interfaces:

**Devenv**: Nice wrappers for common languages and services

```nix
# devenv.nix
{ pkgs, ... }:

{
  languages.javascript.enable = true;
  languages.python.enable = true;

  services.postgres.enable = true;
  services.redis.enable = true;
}
```

**Devbox**: Skip Nix language entirely, use CLI and JSON

```json
{
  "packages": ["nodejs@20", "python@3.11", "postgresql@15"],
  "shell": {
    "init_hook": "echo 'Environment ready!'"
  }
}
```

```bash
devbox shell  # Activates environment
```

#### Nix vs Containers

| Aspect | Nix | Containers |
|--------|-----|------------|
| **Paradigm** | Declarative packages | Packaged filesystem |
| **Isolation** | Process-level (shared kernel) | Strong (separate filesystem) |
| **Disk usage** | Shared dependencies | Duplicated layers |
| **Speed** | Instant activation (if cached) | Seconds to start container |
| **Portability** | Linux, macOS (limited Windows) | Linux (or Linux VM on Windows/Mac) |
| **Learning curve** | Steep (Nix language) | Moderate (Dockerfile syntax) |

**When to use Nix**:

- **Reproducible builds** - Exact same environment across machines
- **Multiple projects** - Shared dependencies save disk space
- **Native performance** - No container overhead
- **Language ecosystems** - Nix has 80,000+ packages

**When to use containers**:

- **Team standardization** - Easier for non-Nix users
- **Production parity** - Develop in same environment as deployment
- **Strong isolation** - Separate filesystem from host

---

## Comparison Matrix

### Quick Reference Table

| Feature | Dev Containers | WSL2 | Traditional VMs | Raw Docker | Codespaces/Gitpod | Nix + direnv |
|---------|---------------|------|-----------------|------------|-------------------|--------------|
| **Isolation** | Container | Managed VM | Full VM | Container | Container (cloud) | Process-level |
| **Boot time** | 10-30s | 2-5s | 1-5min | 5-10s | 30-60s | Instant (cached) |
| **Disk overhead** | 100MB-1GB | 5-10GB | 10-40GB | 100MB-1GB | 0 (cloud) | ~100MB-500MB |
| **RAM overhead** | Minimal | Dynamic | Fixed allocation | Minimal | 0 (cloud) | None |
| **Performance** | Near-native | Near-native | 5-10% penalty | Near-native | Network-dependent | Native |
| **Platform** | Win/Mac/Linux | Windows only | All | Win/Mac/Linux | Cloud (any device) | Linux, macOS |
| **Editor support** | VSCode, JetBrains, CLI | Any | Any | Terminal/Manual | VSCode, JetBrains | Any |
| **Team consistency** | Excellent | Good (within Windows) | Good | Moderate | Excellent | Excellent (if Nix) |
| **Dotfiles** | Auto-integration | Native Linux | Native | Manual | Auto-integration | Native |
| **Learning curve** | Low | Low | Moderate | Moderate | Low | High (Nix language) |
| **Cost** | Free (local) | Free (Windows) | Free | Free (local) | $$$ (cloud hours) | Free |

### Performance Deep Dive

**File I/O Performance** (relative to native):

| Environment | Local filesystem | Cross-boundary | Network |
|-------------|-----------------|----------------|---------|
| **Native** | 100% | N/A | 100% |
| **WSL2** | 95-100% (in Linux FS) | 20-40% (/mnt/c) | 95% |
| **Dev container** | 90-95% (volumes) | 50-70% (bind mounts) | 95% |
| **Traditional VM** | 90-95% | 60-80% (shared folders) | 90% |
| **Codespaces** | 100% (server-side) | N/A | Varies (latency) |
| **Nix** | 100% | N/A | 100% |

**Best practices**:

- **WSL2**: Keep files in Linux filesystem (`~/projects`), not Windows (`/mnt/c`)
- **Dev containers**: Use named volumes for node_modules, caches
- **Traditional VMs**: Avoid shared folders for intensive I/O (Git, builds)

### Resource Usage Patterns

**Typical resource consumption** (4-core CPU, 16GB RAM host):

| Environment | Idle RAM | Active Development | Peak (build) |
|-------------|----------|-------------------|--------------|
| **Native** | 0 | 0 | 0 (host resources) |
| **WSL2** | 80MB | 200MB-1GB | 2-4GB |
| **Dev container** | 50MB | 300MB-2GB | 2-6GB |
| **Traditional VM** | 2GB (reserved) | 4-8GB (reserved) | 4-8GB |
| **Nix** | 0 | 0 | 0-2GB (build cache) |

---

## Use Case Analysis

### Personal Development (macOS/Linux Native)

**Recommended approach**: Native development with dotfiles

**Rationale**:

- No performance overhead
- Full access to all system features
- Dotfiles provide the primary environment consistency
- No need for containerization unless testing production environment

**When to add containers**:

- **Multi-version testing** - Test against Python 3.9, 3.10, 3.11 simultaneously
- **Isolated experiments** - Try new tools without polluting system
- **Production parity** - Development container matches deployed container

**Workflow**:

```bash
# Primary development: native
git clone repo && cd repo
npm install  # Uses system Node.js managed by nvm
npm run dev

# Testing in container when needed
docker run -it --rm -v $(pwd):/workspace -w /workspace node:20 npm test
```

**Dotfiles setup**:

- Clone and install dotfiles once: `~/dotfiles/install.sh`
- Symlinks to `~/.config`, `~/.zshrc`, etc.
- Full feature set: custom shell functions, themes, aliases, tools

---

### Windows Development (WSL2 + Docker)

**Recommended approach**: WSL2 as primary environment + dev containers for projects

**Architecture**:

```text
Windows Host
├── WSL2 (Ubuntu)
│   ├── Dotfiles installed (full Linux environment)
│   ├── Docker installed (docker.io or Docker Desktop)
│   ├── Primary development (terminal, editors)
│   └── Dev containers run here
└── Windows apps
    ├── VSCode (connects to WSL2)
    ├── Browser
    └── Other GUI tools
```

**Workflow**:

```bash
# In Windows: Open terminal, enter WSL2
wsl

# In WSL2: Full Linux environment with dotfiles
cd ~/projects/my-app

# Option 1: Native development in WSL2
npm install && npm run dev

# Option 2: Open in dev container (VSCode)
code .  # VSCode connects to WSL2, detects .devcontainer, offers to reopen in container
```

**Dotfiles deployment**:

```bash
# Inside WSL2 - identical to macOS/Linux
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh

# Result: Full Linux environment
# - Zsh with custom config
# - Tmux, Neovim, fzf, all configured
# - Shell functions, aliases
# - Same experience as personal macOS/Linux machines
```

**Benefits of this hybrid**:

- **WSL2** provides native Linux for daily work
- **Full dotfiles** installed in WSL2 = productivity on par with macOS/Linux
- **Dev containers** ensure team project consistency without sacrificing personal environment
- **Docker in WSL2** = native Linux kernel, better performance than Docker Desktop on Windows

---

### Team Development (Consistency vs Personalization)

**Challenge**: Balance project-level consistency with individual productivity.

**Recommended approach**: Dev containers for project + personal dotfiles

**Architecture**:

```text
Project Repository
├── .devcontainer/
│   ├── devcontainer.json       ← Team-defined: tools, versions, extensions
│   └── Dockerfile              ← Team-defined: base image, dependencies
└── (project files)

Developer's Machine
├── VSCode Settings
│   └── dotfiles.repository     ← Personal: shell config, aliases, tools
└── Container Runtime
    ├── Project container       ← Shared: Node.js 20, PostgreSQL 15, ESLint
    └── Personal dotfiles       ← Individual: custom prompt, git aliases, vim config
```

**Example devcontainer.json** (project-level):

```json
{
  "name": "My Project Dev Environment",
  "image": "mcr.microsoft.com/devcontainers/typescript-node:20",

  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },

  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "ms-azuretools.vscode-docker"
      ]
    }
  },

  "forwardPorts": [3000, 5432],

  "postCreateCommand": "npm install",

  "remoteUser": "node"
}
```

**Personal dotfiles integration** (individual developer settings):

```json
// VSCode settings.json (user-level, not in project)
{
  "dotfiles.repository": "https://github.com/myusername/dotfiles",
  "dotfiles.targetPath": "~/dotfiles",
  "dotfiles.installCommand": "install.sh"
}
```

**Result**:

- **Team consistency**: Everyone has Node.js 20, PostgreSQL 15, same linters
- **Personal productivity**: Each developer has their shell config, aliases, custom tools
- **Onboarding**: New developer clones repo, opens in container, ready in minutes

**What goes where**:

| Configuration | Location | Example |
|--------------|----------|---------|
| **Project** | `.devcontainer/` | Runtime versions, databases, project extensions |
| **Team standards** | `.devcontainer/` | Linters, formatters, testing frameworks |
| **Personal shell** | Dotfiles repo | Zsh theme, git aliases, tmux config |
| **Personal editor** | Dotfiles repo or user settings | Vim keybindings, custom snippets |

---

### Contractor/Restricted Environments

**Scenario 1: Windows VM without WSL** (corporate restrictions)

**Recommended approach**: Docker + dev containers

```bash
Windows VM (Restricted)
├── Docker Desktop
└── VSCode with Dev Containers extension

Workflow:
1. Clone project repository
2. VSCode detects .devcontainer
3. Development happens entirely in container
4. Minimal dotfiles (shell basics in container)
```

**Limitations**:

- No native Linux environment for daily work
- Reduced productivity without full dotfiles
- Dependent on project having devcontainer configuration

**Minimal dotfiles in container**:

Since you don't control the Windows environment, focus on container-based dotfiles:

```json
// devcontainer.json
{
  "image": "ubuntu:22.04",
  "postCreateCommand": "bash /tmp/setup.sh",
  "mounts": [
    "source=${localEnv:HOME}/minimal-dotfiles,target=/tmp/dotfiles,type=bind"
  ]
}
```

```bash
# /tmp/setup.sh
#!/usr/bin/env bash
cp /tmp/dotfiles/.bashrc ~/.bashrc
cp /tmp/dotfiles/.gitconfig ~/.gitconfig
# Minimal setup - just essentials
```

**Scenario 2: Windows VM with Docker, no admin rights**

**Recommended approach**: Docker + cloud development (Codespaces/Gitpod)

If Docker Desktop requires admin rights and you can't install it:

- **GitHub Codespaces** - No local installation needed, runs in browser
- **Gitpod** - Cloud workspaces, connect from any machine

**Dotfiles via Codespaces**:

```json
// GitHub account settings → Codespaces
{
  "dotfiles": true,
  "dotfiles_repository": "username/dotfiles",
  "dotfiles_install_command": "install.sh"
}
```

Every Codespace automatically includes your dotfiles, providing a consistent environment despite restricted local machine.

**Scenario 3: High-security environment (air-gapped network)**

**Recommended approach**: Traditional VM with dotfiles snapshot

```bash
Base VM Template
├── Ubuntu 22.04 installed
├── Dotfiles pre-installed
├── Development tools pre-installed
└── Snapshot saved

For new projects:
1. Clone base VM
2. Customize for project
3. No internet needed (air-gapped)
```

---

## Dotfiles Integration Patterns

### Native Environments (macOS, Linux, WSL2)

**Full dotfiles feature set** with no restrictions:

```bash
# Clone dotfiles
git clone https://github.com/username/dotfiles ~/dotfiles

# Install via symlink manager
cd ~/dotfiles
./install.sh  # or task symlinks:link, etc.

# Result: Symlinks to all configurations
~/.config/nvim → ~/dotfiles/platforms/common/.config/nvim
~/.zshrc → ~/dotfiles/platforms/common/.config/zsh/.zshrc
~/.tmux.conf → ~/dotfiles/platforms/common/.config/tmux/tmux.conf
```

**Capabilities**:

- Custom shell functions and aliases
- Complex tools (Neovim plugins, tmux configurations)
- System-wide settings (Git config, SSH config)
- Shell theme synchronization (theme-sync, base16)
- Personal CLI applications (menu, notes, sess)

**Shell libraries integration**:

If your dotfiles provide shell libraries (like this repo's `logging.sh`, `formatting.sh`, `error-handling.sh`):

```bash
# In scripts inside native environment
source "$HOME/.local/shell/logging.sh"
log_info "Starting backup..."
```

---

### Dev Containers (Layered Approach)

**Philosophy**: Project container + personal dotfiles layer

**Two-stage setup**:

1. **Project base** (`.devcontainer/devcontainer.json`) - Team-shared tools
2. **Personal overlay** (dotfiles) - Individual customization

**Example: Comprehensive devcontainer with dotfiles**

```json
{
  "name": "Full-featured development environment",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",

  "features": {
    "ghcr.io/devcontainers/features/node:1": {"version": "20"},
    "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },

  "postCreateCommand": "bash .devcontainer/setup-dotfiles.sh",

  "mounts": [
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,readonly,type=bind",
    "source=${localEnv:HOME}/.gitconfig,target=/home/vscode/.gitconfig,type=bind"
  ],

  "containerEnv": {
    "DOTFILES_REPO": "https://github.com/${localEnv:GITHUB_USER}/dotfiles"
  },

  "customizations": {
    "vscode": {
      "settings": {
        "terminal.integrated.defaultProfile.linux": "zsh"
      },
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode"
      ]
    }
  }
}
```

**Setup script** (`.devcontainer/setup-dotfiles.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Installing dotfiles in container..."

# Clone dotfiles if DOTFILES_REPO is set
if [ -n "${DOTFILES_REPO:-}" ]; then
  git clone "$DOTFILES_REPO" ~/dotfiles
  cd ~/dotfiles

  # Run minimal install (not full system install)
  ./install-minimal.sh  # Subset: shell config, aliases, not system packages
fi

# Install Zsh if not present
if ! command -v zsh &> /dev/null; then
  sudo apt-get update && sudo apt-get install -y zsh
fi

# Set Zsh as default shell
sudo chsh -s "$(which zsh)" "$(whoami)"

echo "Dotfiles setup complete!"
```

**Dotfiles repository structure** for container compatibility:

```bash
dotfiles/
├── install.sh              # Full installation (native systems)
├── install-minimal.sh      # Container installation (no system packages)
├── platforms/common/
│   ├── .config/
│   │   ├── zsh/            # Shell config (works in containers)
│   │   ├── git/            # Git config (works in containers)
│   │   └── nvim/           # Neovim config (if Neovim in container)
│   └── .local/
│       ├── bin/            # Personal scripts (portable)
│       └── shell/          # Shell libraries (portable)
└── README.md
```

**install-minimal.sh** (container-safe):

```bash
#!/usr/bin/env bash
# Minimal dotfiles install for containers - no system package installation

set -euo pipefail

DOTFILES_DIR="$HOME/dotfiles"

# Symlink shell configurations
ln -sf "$DOTFILES_DIR/platforms/common/.config/zsh/.zshrc" "$HOME/.zshrc"
ln -sf "$DOTFILES_DIR/platforms/common/.config/git/.gitconfig" "$HOME/.gitconfig"

# Symlink personal scripts
mkdir -p "$HOME/.local/bin"
ln -sf "$DOTFILES_DIR/platforms/common/.local/bin/"* "$HOME/.local/bin/"

# Source shell libraries in .zshrc (or .bashrc)
# They'll be available in container shells
```

**What works well in containers**:

- Shell aliases and functions
- Git configuration (user, aliases, diff tools)
- Editor configurations (Neovim, Vim, Emacs)
- Terminal multiplexer configs (tmux)
- Personal scripts and tools (shell, Python, Go apps)

**What doesn't work or needs adaptation**:

- System package installation (no sudo or permission issues)
- GUI applications (no X server typically)
- System-level settings (network, security policies)
- Services (Docker daemon, databases - use devcontainer features instead)

---

### WSL2 (Native Linux with Windows Interop)

**Approach**: Identical to macOS/Linux (it's real Linux)

**Installation**:

```bash
# Inside WSL2 (Ubuntu, Debian, etc.)
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh  # Full installation - same as native Linux
```

**Windows interop considerations**:

```bash
# WSL2 has access to Windows filesystem
/mnt/c/Users/YourName/...  # Windows C:\ drive

# Git config consideration - use Linux Git, not Windows Git
# Avoid CRLF issues by working in Linux filesystem (~/projects)
```

**Best practice**:

- **Store projects** in Linux filesystem (`~/projects`), not Windows (`/mnt/c`)
- **Install tools** via Linux package managers (apt, snap), not Windows
- **Use dotfiles** as if on native Linux - no special considerations

**Performance**:

- Files in Linux FS (`~/*`): near-native speed
- Files in Windows FS (`/mnt/c/*`): slower (filesystem translation layer)

---

### Traditional VMs

**Approach**: Same as native installation (full OS control)

**Dotfiles workflow**:

```bash
# Inside VM (Ubuntu, Fedora, etc.)
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh
```

**Sharing dotfiles across multiple VM instances**:

**Option 1: Snapshot after dotfiles installation**

```bash
1. Create base VM
2. Install dotfiles
3. Take snapshot: "Base + Dotfiles"
4. Clone VM from snapshot for each project
```

**Option 2: Shared folder with symlinks**

```text
Host Machine
└── ~/dotfiles (shared with VMs)

VM
└── /mnt/host-dotfiles → symlink to shared folder
    ~/.zshrc → /mnt/host-dotfiles/platforms/common/.config/zsh/.zshrc
```

**Option 3: Configuration management**

```bash
# Ansible playbook
- hosts: dev-vms
  tasks:
    - name: Clone dotfiles
      git:
        repo: https://github.com/username/dotfiles
        dest: ~/dotfiles
    - name: Install dotfiles
      command: ~/dotfiles/install.sh
```

---

## Decision Framework

### Decision Tree

```bash
Start: Choose development environment
│
├─ Windows machine?
│  ├─ Yes: WSL2 available?
│  │  ├─ Yes → Use WSL2 as primary + dev containers for projects
│  │  └─ No: Admin rights for Docker?
│  │     ├─ Yes → Docker Desktop + dev containers
│  │     └─ No → Cloud development (Codespaces/Gitpod)
│  └─ No: macOS or Linux?
│     └─ Yes → Native development + selective containerization
│
├─ Team project with multiple contributors?
│  └─ Yes → Dev containers for consistency
│
├─ Need to test multiple OS versions?
│  └─ Yes → Traditional VMs or Docker containers
│
├─ Building with complex dependencies?
│  ├─ Prefer declarative approach → Nix + direnv
│  └─ Prefer containers → Docker or dev containers
│
└─ Working alone on personal projects?
   └─ Native + dotfiles (simplest, fastest)
```

### Hybrid Approaches

**WSL2 + Dev Containers** (recommended for Windows development):

```bash
Daily work in WSL2:
- Shell with full dotfiles
- Git operations
- File editing
- Terminal-based tools

Project work in dev containers:
- Team-consistent tooling
- Isolated dependencies
- Reproducible builds
```

**Native + Docker for Testing** (macOS/Linux):

```bash
Primary development:
- Native environment (fastest)
- Full dotfiles

Integration testing:
- Docker containers (production parity)
- docker-compose for multi-service testing
```

**Nix + Dev Containers** (advanced):

```bash
Nix for language runtimes:
- Node.js, Python, Go versions per project
- Fast activation with direnv

Dev containers for team projects:
- VSCode team using devcontainer
- You use devcontainer CLI + Nix shell
```

### Migration Paths

**From native to containers**:

1. Create `.devcontainer/devcontainer.json` in project
2. Define base image and tools
3. Configure dotfiles integration (`dotfiles.repository`)
4. Test: Open project in container, verify functionality
5. Document for team in README

**From VMs to WSL2** (Windows users):

1. Export/backup data from VM
2. Install WSL2: `wsl --install`
3. Install Linux distro: `wsl --install -d Ubuntu`
4. Clone dotfiles in WSL2: `git clone ... ~/dotfiles && cd ~/dotfiles && ./install.sh`
5. Migrate projects to WSL2 filesystem: `~/projects/`

**From Docker to Nix**:

1. Install Nix: `sh <(curl -L https://nixos.org/nix/install)`
2. Create `flake.nix` defining dependencies
3. Add `.envrc` with `use flake`
4. Run `direnv allow`
5. Test: Dependencies loaded automatically on `cd`

---

## Real-World Scenarios

### Scenario 1: Personal Computers (macOS + Arch Linux)

**Environment**: macOS personal laptop + Arch Linux desktop

**Approach**: Native development with unified dotfiles

**Setup**:

```bash
# On both machines
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh  # Detects platform, installs accordingly
```

**Dotfiles repository structure** (platform-aware):

```text
dotfiles/
├── platforms/
│   ├── common/          # Shared configs (Neovim, tmux, zsh)
│   ├── macos/           # macOS-specific (Alfred, BetterTouchTool)
│   └── arch/            # Arch-specific configs
├── install.sh           # Detects platform, symlinks appropriate configs
└── management/
    └── symlinks/        # Symlink manager (handles platform differences)
```

**Benefits**:

- Consistent environment across machines
- Platform-specific overrides (macOS GUI apps, Arch packages)
- Full productivity - no container overhead
- Native performance

**When to use containers**:

- Testing deployment environment (Docker)
- Isolating experiments (trying new tools without polluting system)

---

### Scenario 2: Work Laptop (Windows + WSL2 + Docker)

**Environment**: Windows 11 work laptop with WSL2 and Docker Desktop

**Approach**: WSL2 as primary environment + dev containers for team projects

**Setup**:

```powershell
# In PowerShell (Windows)
wsl --install -d Ubuntu

# Enter WSL2
wsl

# In WSL2 (Ubuntu) - now a native Linux environment
git clone https://github.com/username/dotfiles ~/dotfiles
cd ~/dotfiles
./install.sh  # Full Linux installation

# Install Docker in WSL2 (or use Docker Desktop)
# Docker Desktop automatically integrates with WSL2

# VSCode with Remote-WSL and Dev Containers extensions
```

**Daily workflow**:

```bash
# Morning: Launch terminal, enter WSL2
wsl

# Full Linux environment with dotfiles active:
# - Custom zsh theme
# - tmux configured
# - Neovim with plugins
# - Custom aliases and functions
# - Personal CLI tools (menu, notes, etc.)

# Solo project: work natively in WSL2
cd ~/projects/personal-app
npm run dev  # Uses Node.js installed in WSL2

# Team project: open in dev container
cd ~/projects/team-api
code .
# VSCode detects .devcontainer, prompts to reopen in container
# Container has team-defined tools + your personal dotfiles
```

**Architecture**:

```bash
Windows 11 Host
│
├── WSL2 (Ubuntu 22.04)
│   ├── Dotfiles (full installation)
│   │   ├── Zsh + custom config
│   │   ├── Tmux + custom config
│   │   ├── Neovim + 50+ plugins
│   │   ├── Shell functions library
│   │   └── Personal apps (menu, notes, theme-sync)
│   │
│   ├── Docker daemon (via Docker Desktop or native)
│   │
│   └── Projects
│       ├── personal-app/ (native WSL2 development)
│       └── team-api/ (dev container when opened in VSCode)
│
└── Windows Applications
    ├── VSCode (connects to WSL2)
    ├── Browser (Edge/Chrome)
    └── Slack, Teams, etc.
```

**Result**:

- **Productivity**: Full Linux environment with dotfiles = same experience as personal macOS/Arch machines
- **Team consistency**: Dev containers for team projects ensure everyone has same tooling
- **Performance**: WSL2 near-native speed, much better than traditional VMs
- **Best of both worlds**: Windows for corporate apps, Linux for development

---

### Scenario 3: Contractor VMs (Windows, possibly no WSL)

**Environment**: Windows VM provided by client, restricted permissions, possibly no WSL2

**Constraints**:

- No admin rights (can't enable WSL2)
- May or may not have Docker Desktop installed
- Limited software installation allowed
- Must use client-provided VM image

**Approach 1: Docker available → Dev containers**

```bash
Windows VM
├── Docker Desktop (pre-installed by client)
└── VSCode (installed by client or portable version)

Workflow:
1. Clone project with .devcontainer
2. VSCode opens project in container
3. Minimal dotfiles in container (can't install everything)
```

**Minimal dotfiles for container**:

Create `dotfiles-minimal` repository with just shell basics:

```text
dotfiles-minimal/
├── .bashrc           # Basic shell config
├── .gitconfig        # Git aliases
├── .vimrc            # Basic Vim config (no plugins)
└── install.sh        # Symlink script (no sudo)
```

```json
// VSCode settings.json
{
  "dotfiles.repository": "https://github.com/username/dotfiles-minimal",
  "dotfiles.installCommand": "bash install.sh"
}
```

**Approach 2: No Docker, internet access → Cloud development**

```bash
GitHub Codespaces workflow:
1. Push code to GitHub
2. Create Codespace from repository
3. Full dotfiles automatically loaded (configured in GitHub settings)
4. Develop in browser or VSCode desktop connected to Codespace
```

**GitHub Codespaces dotfiles setup**:

```json
// GitHub account settings → Codespaces → Dotfiles
{
  "dotfiles_repository": "username/dotfiles",
  "dotfiles_install_command": "install.sh"
}
```

Every Codespace includes your dotfiles - consistent environment despite restricted VM.

**Approach 3: No Docker, no cloud access → Compromise**

If truly restricted (no Docker, no cloud, no admin rights):

1. **Portable VSCode** - Run VSCode from USB drive or user directory
2. **Portable Git** - PortableGit for Windows
3. **Minimal customization** - `.gitconfig`, VSCode settings.json (user-level)

```yaml
User directory:
C:\Users\YourName\
├── PortableApps\
│   ├── VSCode\
│   └── Git\
├── .gitconfig        # Git config (limited customization)
└── AppData\Roaming\Code\User\
    └── settings.json  # VSCode settings
```

**Recommendation**: If possible, request Docker Desktop installation or cloud development access. Restricted Windows VMs without these tools significantly reduce productivity.

---

## Example Configurations

### Example 1: Basic devcontainer.json with Dotfiles

**Scenario**: Node.js project with automatic dotfiles integration

```json
{
  "name": "Node.js Development",
  "image": "mcr.microsoft.com/devcontainers/javascript-node:20",

  "features": {
    "ghcr.io/devcontainers/features/git:1": {},
    "ghcr.io/devcontainers/features/github-cli:1": {}
  },

  "customizations": {
    "vscode": {
      "extensions": [
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode"
      ]
    }
  },

  "forwardPorts": [3000],

  "postCreateCommand": "npm install"
}
```

**Dotfiles via VSCode settings** (`settings.json`):

```json
{
  "dotfiles.repository": "https://github.com/username/dotfiles",
  "dotfiles.targetPath": "~/dotfiles",
  "dotfiles.installCommand": "install-minimal.sh"
}
```

---

### Example 2: Advanced Dockerfile for Development

**Scenario**: Full development environment with multiple languages and tools

```dockerfile
# .devcontainer/Dockerfile
FROM ubuntu:22.04

# Avoid prompts during package installation
ARG DEBIAN_FRONTEND=noninteractive

# Install base tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    sudo \
    zsh \
    tmux \
    neovim \
    ripgrep \
    fd-find \
    fzf \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Python 3.11
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Switch to non-root user
USER $USERNAME
WORKDIR /home/$USERNAME

# Install dotfiles (run as user)
ARG DOTFILES_REPO
RUN if [ -n "$DOTFILES_REPO" ]; then \
    git clone "$DOTFILES_REPO" ~/dotfiles \
    && cd ~/dotfiles \
    && bash install-minimal.sh; \
    fi

# Set Zsh as default shell
RUN sudo chsh -s $(which zsh) $USERNAME

CMD ["/bin/zsh"]
```

**devcontainer.json** using custom Dockerfile:

```json
{
  "name": "Full Development Environment",
  "build": {
    "dockerfile": "Dockerfile",
    "args": {
      "DOTFILES_REPO": "${localEnv:DOTFILES_REPO}"
    }
  },

  "customizations": {
    "vscode": {
      "settings": {
        "terminal.integrated.defaultProfile.linux": "zsh"
      },
      "extensions": [
        "ms-python.python",
        "dbaeumer.vscode-eslint"
      ]
    }
  },

  "forwardPorts": [3000, 5432],

  "remoteUser": "devuser"
}
```

**Usage**:

```bash
# Set environment variable before opening in container
export DOTFILES_REPO="https://github.com/myusername/dotfiles"

# Open in VSCode
code .
# VSCode builds Dockerfile with dotfiles, opens container
```

---

### Example 3: Shell Bootstrap Script for Containers

**Scenario**: Portable dotfiles installation script that works in containers, VMs, and native systems

```bash
#!/usr/bin/env bash
# install-minimal.sh - Container-safe dotfiles installation

set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing minimal dotfiles for container environment..."

# Detect if we're in a container
in_container() {
  [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null
}

# Create necessary directories
mkdir -p "$HOME/.config"
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/shell"

# Symlink shell configuration
echo "Symlinking shell config..."
ln -sf "$DOTFILES_DIR/platforms/common/.config/zsh/.zshrc" "$HOME/.zshrc"
ln -sf "$DOTFILES_DIR/platforms/common/.config/bash/.bashrc" "$HOME/.bashrc"

# Symlink Git configuration
echo "Symlinking Git config..."
ln -sf "$DOTFILES_DIR/platforms/common/.config/git/.gitconfig" "$HOME/.gitconfig"
ln -sf "$DOTFILES_DIR/platforms/common/.config/git/.gitignore_global" "$HOME/.gitignore_global"

# Symlink personal scripts
echo "Symlinking personal scripts..."
for script in "$DOTFILES_DIR/platforms/common/.local/bin/"*; do
  ln -sf "$script" "$HOME/.local/bin/$(basename "$script")"
done

# Symlink shell libraries
echo "Symlinking shell libraries..."
for lib in "$DOTFILES_DIR/platforms/common/.local/shell/"*; do
  ln -sf "$lib" "$HOME/.local/shell/$(basename "$lib")"
done

# Symlink Neovim config if Neovim is installed
if command -v nvim &> /dev/null; then
  echo "Symlinking Neovim config..."
  ln -sf "$DOTFILES_DIR/platforms/common/.config/nvim" "$HOME/.config/nvim"
fi

# Symlink tmux config if tmux is installed
if command -v tmux &> /dev/null; then
  echo "Symlinking tmux config..."
  ln -sf "$DOTFILES_DIR/platforms/common/.config/tmux/tmux.conf" "$HOME/.tmux.conf"
fi

# Container-specific setup
if in_container; then
  echo "Container detected - skipping system package installation"
else
  echo "Native system detected - consider running full install.sh instead"
fi

echo "Minimal dotfiles installation complete!"
echo "Restart your shell or run: source ~/.zshrc"
```

**Usage**:

```bash
# In devcontainer postCreateCommand
"postCreateCommand": "bash ~/dotfiles/install-minimal.sh"

# In VM or WSL2 (full installation)
bash ~/dotfiles/install.sh

# In restricted container (minimal)
bash ~/dotfiles/install-minimal.sh
```

---

### Example 4: VSCode Settings for Dotfiles Repository

**Scenario**: Configure VSCode to automatically use your dotfiles in all dev containers

```json
{
  // Dotfiles configuration for dev containers
  "dotfiles.repository": "https://github.com/username/dotfiles",
  "dotfiles.targetPath": "~/dotfiles",
  "dotfiles.installCommand": "bash install-minimal.sh",

  // Dev Containers settings
  "dev.containers.defaultExtensions": [
    "eamodio.gitlens",
    "GitHub.copilot"
  ],

  // Terminal settings
  "terminal.integrated.defaultProfile.linux": "zsh",
  "terminal.integrated.profiles.linux": {
    "zsh": {
      "path": "/bin/zsh"
    }
  },

  // Git settings
  "git.enableCommitSigning": true,
  "git.confirmSync": false,

  // Editor settings
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

---

## Conclusion

Choosing a development environment involves balancing consistency, performance, isolation, and productivity. The landscape in 2025 offers mature solutions for every scenario:

- **Dev containers** provide team consistency while remaining editor-agnostic
- **WSL2** transforms Windows into a viable Linux development platform
- **Cloud development** eliminates local constraints for restricted environments
- **Nix** offers declarative reproducibility for those willing to learn

**Dotfiles remain central** to developer productivity across all approaches. Whether running natively, in containers, or in the cloud, personalizing your shell, editor, and tools makes development efficient and enjoyable.

The best environment is the one that minimizes friction between you and your code. Start simple (native + dotfiles), add complexity only when collaboration or consistency demands it.

---

## References

### Dev Containers

- [Developing inside a Container - VSCode Docs](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Containers tutorial](https://code.visualstudio.com/docs/devcontainers/tutorial)
- [Introduction to dev containers - GitHub Docs](https://docs.github.com/codespaces/setting-up-your-project-for-codespaces/introduction-to-dev-containers)
- [Supporting tools and services](https://containers.dev/supporting)
- [DevPod: SSH-Based Devcontainers Without IDE Lock-in](https://fabiorehm.com/blog/2025/11/11/devpod-ssh-devcontainers/)
- [Devcontainers in 2025: A Personal Take](https://ivanlee.me/devcontainers-in-2025-a-personal-take/)
- [What Is DevContainer? Why Every Developer Will Use It Soon (2025 Guide)](https://devtechinsights.com/what-is-devcontainer-developers-2025/)

### WSL2, VMs, and Containers

- [Comparing WSL Versions - Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/compare-versions)
- [Docker container in Server 2025: Windows vs. Hyper-V vs. WSL2](https://4sysops.com/archives/docker-container-in-server-2025-windows-vs-hyper-v-vs-wsl2/)
- [WSL vs Virtual Machine: Compare Performance, Features & Use Cases](https://www.diskinternals.com/vmfs-recovery/wsl-vs-virtual-machine/)
- [Hyper-V vs WSL: How To Pick The Right Tool?](https://pmbanugo.me/blog/hyperv-wsl-on-windows)

### Dotfiles Integration

- [Dotfiles in a Workspace - DevPod docs](https://devpod.sh/docs/developing-in-workspaces/dotfiles-in-a-workspace)
- [Ultimate Guide to Dev Containers](https://www.daytona.io/dotfiles/ultimate-guide-to-dev-containers)
- [Dev Environment as a Code (DEaaC) with DevContainers, Dotfiles, and GitHub Codespaces](https://nikiforovall.blog/productivity/devcontainers/2022/08/13/deaac.html)
- [Adopting Dotfiles for Codespaces and DevContainers](https://blog.v-lad.org/adopting-dotfiles-for-codespaces-and-dev-containers/)

### Remote Development

- [Gitpod vs. Codespaces vs. Coder vs. DevPod: 2024 Comparison](https://www.vcluster.com/blog/comparing-coder-vs-codespaces-vs-gitpod-vs-devpod)
- [Gitpod vs. Codespaces: How to Choose](https://www.devzero.io/blog/gitpod-vs-codespace)
- [7 Remote Development Platforms in 2025](https://dev.to/diploi/7-remote-development-platforms-in-2025-to-code-without-a-local-setup-1f92)

### Nix + direnv

- [Effortless dev environments with Nix and direnv](https://determinate.systems/blog/nix-direnv/)
- [Easy development environments with Nix and Nix flakes!](https://dev.to/arnu515/easy-development-environments-with-nix-and-nix-flakes-21mb)
- [Automated Environments with Nix flakes, Direnv, Devshell, and Starship](https://esras.blog/automated-environments-with-nix-flakes-direnv-devshell-and-starship/)
