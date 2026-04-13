# Package Differences

Package name and binary name differences across platforms.

## Package Name Differences

Many tools have different package names across platforms. This table maps the tool name to its package name on each platform.

| Tool Name     | macOS (brew) | Ubuntu (apt)     | Arch (pacman) | Notes                              |
| ------------- | ------------ | ---------------- | ------------- | ---------------------------------- |
| **bat**       | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **eza**       | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **fd**        | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **ripgrep**   | `ripgrep`    | `ripgrep`        | `ripgrep`     | All platforms use `rg` binary      |
| **fzf**       | `fzf`        | `fzf`            | `fzf`         | ✅ Consistent                      |
| **zoxide**    | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **neovim**    | `neovim`     | `neovim`         | `neovim`      | All use `nvim` binary              |
| **tmux**      | `tmux`       | `tmux`           | `tmux`        | ✅ Consistent                      |
| **lazygit**   | `lazygit`    | via snap/release | `lazygit`     | Ubuntu needs manual install        |
| **yazi**      | `yazi`       | via cargo        | `yazi`        | Ubuntu needs Rust                  |
| **git-delta** | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **broot**     | cargo-binstall | cargo-binstall | cargo-binstall | Installed via Rust on all platforms |
| **jq**        | `jq`         | `jq`             | `jq`          | ✅ Consistent                      |
| **yq**        | `yq`         | snap or binary   | `yq`          | Ubuntu via snap or manual          |
| **htop**      | `htop`       | `htop`           | `htop`        | ✅ Consistent                      |
| **tree**      | `tree`       | `tree`           | `tree`        | ✅ Consistent                      |
| **go-task**   | `go install` | `go install`     | `go install`  | Installed via Go on all platforms  |

## Binary Name Differences

With the current installation strategy (cargo-binstall for Rust tools, GitHub releases for others), binary names are consistent across all platforms. No symlinks or workarounds needed.

## Rust/Cargo Installation

Rust and cargo-binstall are installed on **all platforms** for consistent Rust tool management:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
cargo install cargo-binstall
```

### Cargo-Installed Tools (All Platforms)

These tools are installed via `cargo-binstall` (pre-compiled binaries, fast) on all platforms:

- `bat` - cat alternative
- `fd-find` - find alternative
- `eza` - ls alternative
- `zoxide` - cd alternative
- `git-delta` - git diff viewer
- `oxker` - Docker container TUI
- `broot` - interactive directory tree navigator

Installation is handled by `install/common/language-tools/cargo-tools.sh`.
