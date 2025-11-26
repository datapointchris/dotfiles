# WSL Ubuntu Package Version Issues

**Context**: Ubuntu LTS ships conservative package versions that are often too old for modern CLI tools.

## The Problem

Ubuntu 24.04 LTS apt packages for several tools are outdated and cause dependency conflicts:

- **fzf**: apt version too old, missing features
- **yazi**: cargo build fails with jemalloc errors on Ubuntu
- **eza, git-delta**: Not available in apt at all

## The Solution

### fzf - Build from Source

**Why**: Needs latest features, apt version insufficient

```bash
# Requires Go toolchain
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.25.2.linux-386.tar.gz
export PATH=$PATH:/usr/local/go/bin

# Build fzf
cd fzf-directory
make
sudo make install
# Or manually: sudo cp -f target/fzf-linux_amd64 /bin/fzf
```

### yazi - Use Pre-built Binaries or Snap

**Why**: cargo build fails with tikv-jemalloc-sys compilation errors on Ubuntu

**Originally tried**:

```bash
# This FAILS on Ubuntu with jemalloc errors
cargo build --release --locked
```

**Error**:

```yaml
include/jemalloc/internal/rtree.h:106:41: warning: left shift count is negative
error: variably modified 'root' at file scope
```

**Working solutions**:

1. **Pre-built binaries** (current approach):

   ```bash
   curl -L "https://github.com/sxyazi/yazi/releases/download/${VERSION}/yazi-x86_64-unknown-linux-gnu.zip" -o yazi.zip
   unzip yazi.zip
   mv yazi-x86_64-unknown-linux-gnu/yazi ~/.local/bin/
   ```

2. **Snap** (alternative):

   ```bash
   sudo snap install yazi --classic
   ```

**System dependencies required**:

```bash
sudo apt install ffmpeg 7zip jq poppler-utils imagemagick chafa
```

Note: imagemagick may need to be built from source for full functionality

### eza and git-delta - Use Cargo

**Why**: Not available in Ubuntu apt repositories

```bash
source "$HOME/.cargo/env"
cargo install eza
cargo install git-delta
```

### LazyGit - Manual Install

**Why**: apt version often outdated

```bash
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | \grep -Po '"tag_name": *"v\K[^"]*')
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz lazygit
sudo install lazygit -D -t /usr/local/bin/
```

## Key Learnings

1. **Don't trust apt for CLI tools** - Ubuntu LTS prioritizes stability over latest versions
2. **Pre-built binaries > cargo build** - Avoid compilation issues, faster, more reliable
3. **Document system dependencies** - yazi needs 6+ system packages to function
4. **Version check before apt** - Many tools have better installation methods than apt
5. **Rust is required anyway** - Install rustup for eza/delta, but avoid cargo build for complex tools

## Current Automation

Our taskfiles handle this automatically:

- `wsl:install-packages` - apt for what works (bat, fd, fzf via apt is now acceptable)
- `wsl:install-yazi` - downloads pre-built binaries
- `wsl:install-rust` - installs rustup toolchain
- `wsl:install-cargo-tools` - builds eza and git-delta only

## Testing

Use `management/test-wsl-setup.sh -d` to test installation without committing changes.

## Related

- [Package Management Philosophy](../architecture/package-management.md)
- [Troubleshooting](../reference/troubleshooting.md)
