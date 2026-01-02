# Universal Packages Review

Packages currently in macOS Brewfile that should be considered for WSL/Arch:

## Currently Universal ✅

- git, curl, wget, unzip
- ripgrep, tmux, tree, htop, jq
- zsh
- ffmpeg, imagemagick
- shellcheck, shfmt

## Should Be Universal (High Priority)

- **lazydocker** - Docker TUI (currently macOS only)
- **oxker** - Docker container viewer (currently macOS only)
- **glow** - Markdown renderer (currently macOS only)
- **gh** - GitHub CLI (macOS has it, WSL might need it)
- **git-secrets** - Prevent committing secrets
- **duf** - Modern df alternative

## Development Tools (Medium Priority)

- **actionlint** - GitHub Actions linter
- **taplo** - TOML formatter & linter
- **terraform ecosystem** (if doing infrastructure work):
  - terraform
  - terraform-docs
  - terraform-ls
  - terraformer
  - terrascan
  - tflint
- **awscli** - AWS CLI

## Security Tools (Medium Priority)

- **mkcert** - Local SSL certificates
- **gnupg** - GPG encryption (already in WSL as gnupg)
- **gpg-tui** - GPG terminal UI
- **trivy** - Container vulnerability scanner

## Nice to Have (Low Priority)

- **cmatrix** - Matrix effect
- **figlet** - ASCII art text
- **pipes-sh** - Animated pipes
- **sl** - Steam locomotive
- **yt-dlp** - YouTube downloader
- **gource** - Repository visualization
- **graphviz** - Graph visualization

## macOS-Specific (Keep in Brewfile Only)

- borders, sketchybar, terminal-notifier
- mas, duti
- coreutils, gnu-sed, gnu-tar, findutils, grep (GNU tools)
- Python versions (homebrew dependencies)
- Lua ecosystem (ruby, lua, luajit, luarocks, openjdk, sbt, sbcl)

## Notes

- For this refactor: Focus on making current universal packages consistent
- Future work: Add high-priority packages to WSL/Arch
- Some packages may not be available in apt/pacman repos
