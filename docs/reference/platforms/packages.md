# Package Differences

Package name and binary name differences across platforms.

## Package Name Differences

Many tools have different package names across platforms. This table maps the tool name to its package name on each platform.

| Tool Name     | macOS (brew) | Ubuntu (apt)     | Arch (pacman) | Notes                              |
| ------------- | ------------ | ---------------- | ------------- | ---------------------------------- |
| **bat**       | `bat`        | `bat`            | `bat`         | Ubuntu installs as `batcat` binary |
| **eza**       | `eza`        | via cargo        | `eza`         | Not in Ubuntu apt repos            |
| **fd**        | `fd`         | `fd-find`        | `fd`          | Ubuntu installs as `fdfind` binary |
| **ripgrep**   | `ripgrep`    | `ripgrep`        | `ripgrep`     | All platforms use `rg` binary      |
| **fzf**       | `fzf`        | `fzf`            | `fzf`         | ✅ Consistent                      |
| **zoxide**    | `zoxide`     | `zoxide`         | `zoxide`      | ✅ Consistent                      |
| **neovim**    | `neovim`     | `neovim`         | `neovim`      | All use `nvim` binary              |
| **tmux**      | `tmux`       | `tmux`           | `tmux`        | ✅ Consistent                      |
| **lazygit**   | `lazygit`    | via snap/release | `lazygit`     | Ubuntu needs manual install        |
| **yazi**      | `yazi`       | via cargo        | `yazi`        | Ubuntu needs Rust                  |
| **git-delta** | `git-delta`  | via cargo        | `git-delta`   | Ubuntu needs Rust                  |
| **jq**        | `jq`         | `jq`             | `jq`          | ✅ Consistent                      |
| **yq**        | `yq`         | snap or binary   | `yq`          | Ubuntu via snap or manual          |
| **htop**      | `htop`       | `htop`           | `htop`        | ✅ Consistent                      |
| **tree**      | `tree`       | `tree`           | `tree`        | ✅ Consistent                      |
| **go-task**   | `go-task`    | via script       | `go-task`     | Binary name: `task`                |

## Binary Name Differences

Some packages install with different binary names.

=== "Ubuntu/WSL"

    **Different binary names**:

    - `bat` package → `batcat` binary (needs symlink to `bat`)
    - `fd-find` package → `fdfind` binary (needs symlink to `fd`)

    **Solution** (implemented in `taskfiles/wsl.yml`):

    ```bash
    # Create symlinks for differently-named packages
    mkdir -p ~/.local/bin
    ln -sf /usr/bin/batcat ~/.local/bin/bat
    ln -sf /usr/bin/fdfind ~/.local/bin/fd
    ```

=== "macOS"

    No binary name differences. All packages install with expected binary names.

=== "Arch Linux"

    No binary name differences. All packages install with expected binary names.

## Rust/Cargo Installation

Some tools require Rust/Cargo, especially on Ubuntu where they're not available via apt.

**All Platforms**:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```

### Cargo-Installed Tools

=== "Ubuntu/WSL"

    These tools need cargo install:

    - `eza` (modern ls)
    - `yazi` (file manager)
    - `git-delta` (git diff viewer)

    ```bash
    cargo install eza yazi-fm git-delta
    ```

=== "macOS"

    All tools available via Homebrew. Cargo not required for standard toolset.

=== "Arch Linux"

    All tools available via pacman. Cargo not required for standard toolset.
