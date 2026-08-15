# ================================================================
# Multi-Stage Dockerfile for Dotfiles Installer Testing
# ================================================================
# Stage 1: base - OS + user setup
# Stage 2: system-packages - System packages installed (reusable base)
# ================================================================

# ================================================================
# Stage 1: Base OS with user setup
# ================================================================
ARG UBUNTU_VERSION=26.04
FROM ubuntu:${UBUNTU_VERSION} AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Install minimal required packages for running installers.
#
# openssh carries the two-machine exchange. The e2e runs a builder container and
# an offline one on a docker network, and a bundle crosses between them over a
# transport declared exactly the way `ifiles` is on a real machine — so the
# transport code is on the trip rather than beside it. Baked here rather than
# installed at container start because the offline container blackholes hosts and
# must not need apt to reach anything.
RUN apt-get update && \
    apt-get install -y \
    sudo \
    git \
    curl \
    wget \
    ca-certificates \
    file \
    unzip \
    openssh-client \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Create non-root test user with sudo access
RUN useradd -m -s /bin/bash -G sudo testuser && \
    echo "testuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER testuser
WORKDIR /home/testuser

# Create standard user directories for installers
RUN mkdir -p /home/testuser/.local/bin

# ================================================================
# Stage 2: System packages (our reusable base image)
# ================================================================
FROM base AS system-packages

# Switch back to root to install system packages
USER root

# Copy dotfiles repo (the declaration the package install below reads)
COPY --chown=testuser:testuser . /home/testuser/dotfiles/

# Set environment for Docker test mode (skips Docker packages)
ENV DOTFILES_DOCKER_TEST=true
ENV HOME=/home/testuser
# The manifest whose apt list this layer bakes in. Both e2e environments built
# on this image declare the same one, so naming it here is not a second answer.
ENV MACHINE=wsl-work-workstation
WORKDIR /home/testuser/dotfiles

# Configure Git to trust this directory (security check for cross-user access)
# Must be after setting HOME so git config writes to correct location
RUN git config --global --add safe.directory /home/testuser/dotfiles

# The package install runs through the CLI, so this layer needs uv. It must not
# survive the layer: the runtime install is what proves the bootstrap installs uv
# itself, and a uv already on PATH makes that assertion vacuous.
#
# `--source system_packages` is the payload without the configuration rows. Those
# want a login session this build has none of — the scheduled check is a systemd
# user timer, and `systemctl --user` in a build layer has no bus to reach.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/opt/build-uv UV_NO_MODIFY_PATH=1 sh \
    && PATH="/opt/build-uv:$PATH" uv run dotfiles system apply --source system_packages \
    && rm -rf /opt/build-uv "$HOME/.local/share/uv" "$HOME/.cache/uv" "$HOME/dotfiles/.venv"

# Remove baked-in dotfiles — tests provide fresh copy via bind mount at runtime.
# Keeping an empty dir so bind mounts and internal copies have a target.
#
# The recursive chown is not belt-and-braces. This stage runs as root with
# HOME=/home/testuser, so everything it touches lands in the user's home owned by
# root: `git config --global` writes .gitconfig, and the uv bootstrap creates
# .cache, .config/uv, .local/share and .local/state. Deleting the *contents*
# above leaves those parents root-owned, and the install then dies at
# `failed to create directory /home/testuser/.cache/uv: Permission denied` —
# which is every test in the offline and restricted environments, at 7 seconds.
RUN rm -rf /home/testuser/dotfiles \
    && mkdir -p /home/testuser/dotfiles \
    && chown -R testuser:testuser /home/testuser

# Switch back to testuser for subsequent stages
USER testuser
WORKDIR /home/testuser
