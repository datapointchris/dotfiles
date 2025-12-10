# ================================================================
# Multi-Stage Dockerfile for Dotfiles Installer Testing
# ================================================================
# Stage 1: base - OS + user setup
# Stage 2: system-packages - System packages installed (reusable base)
# Stage 3: test-runner - Run installer tests
# ================================================================

# ================================================================
# Stage 1: Base OS with user setup
# ================================================================
FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color

# Install minimal required packages for running installers
RUN apt-get update && \
    apt-get install -y \
    sudo \
    git \
    curl \
    wget \
    ca-certificates \
    file \
    unzip \
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

# Copy dotfiles repo (needed for system-packages.sh)
COPY --chown=testuser:testuser . /home/testuser/dotfiles/

# Set environment for Docker test mode (skips Docker packages)
ENV DOTFILES_DOCKER_TEST=true
ENV HOME=/home/testuser
WORKDIR /home/testuser/dotfiles

# Configure Git to trust this directory (security check for cross-user access)
# Must be after setting HOME so git config writes to correct location
RUN git config --global --add safe.directory /home/testuser/dotfiles

# Run system packages installer
RUN bash management/wsl/install/system-packages.sh

# Switch back to testuser for subsequent stages
USER testuser
WORKDIR /home/testuser

# ================================================================
# Stage 3: Test runner (for running individual installers)
# ================================================================
FROM system-packages AS test-runner

# Dotfiles already copied in system-packages stage
WORKDIR /home/testuser/dotfiles

# Default command runs bash (can be overridden)
CMD ["/bin/bash"]
