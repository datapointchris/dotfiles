# Language Tool Installers

## Pattern

This directory contains installers for tools distributed through language package managers (cargo, npm, go, uv). These scripts read package lists from `packages.yml` and install multiple tools via their respective package managers.

**Key characteristics**:

- Install multiple packages from `packages.yml` in a single run
- Use language-specific package managers (cargo binstall, npm install -g, go install, uv tool install)
- Loop through package list, continue on individual failures
- Report each failure via `output_failure_data()`

## When to Use

Add a new installer to this directory when:

- You need to install multiple tools via a language package manager
- Tools are distributed through package registries (crates.io, npmjs.com, pkg.go.dev, PyPI)
- Package manager is already installed (via language-managers/)
- Packages are defined in `packages.yml`

## Libraries Used

All scripts in this directory source:

```bash
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
# Plus language-specific environment (e.g., $HOME/.cargo/env, nvm.sh)
```

## Standard Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

# Source language environment
source "$HOME/.cargo/env"  # or other environment file

print_banner "Installing Package Manager Tools"

log_info "Reading packages from packages.yml..."
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=cargo | while read -r package; do
  log_info "Installing $package..."
  if cargo binstall -y "$package"; then
    log_success "$package installed"
  else
    manual_steps="Install manually with cargo:
   cargo install $package

Or try cargo-binstall directly:
   cargo binstall -y $package"

    output_failure_data "$package" "https://crates.io/crates/$package" "latest" "$manual_steps" "Failed to install via cargo-binstall"
    log_warning "$package installation failed (see summary)"
  fi
done

log_success "Tools installation complete"
```

## Package Configuration

Packages are defined in `management/packages.yml`:

```yaml
cargo_packages:
  - name: bat
    description: "A cat clone with syntax highlighting"
  - name: fd-find
    description: "A simple, fast alternative to find"

npm_globals:
  language_servers:
    - name: typescript-language-server
      description: "TypeScript language server"

go_tools:
  - package: github.com/go-task/task/v3/cmd/task@latest
    description: "Task runner / build tool"

uv_tools:
  linters:
    - name: ruff
      description: "Fast Python linter"
```

## Adding a New Package

1. **Add to packages.yml**:

   ```yaml
   # For cargo
   cargo_packages:
     - name: toolname
       description: "Tool description"

   # For npm
   npm_globals:
     category:
       - name: toolname
         description: "Tool description"

   # For go
   go_tools:
     - package: github.com/user/repo/cmd/tool@latest
       description: "Tool description"

   # For uv
   uv_tools:
     category:
       - name: toolname
         description: "Tool description"
   ```

2. **Test package installation manually**:

   ```bash
   # Cargo
   cargo binstall -y toolname

   # npm
   npm install -g toolname

   # Go
   go install github.com/user/repo/cmd/tool@latest

   # uv
   uv tool install toolname
   ```

3. **Run installer script**:

   ```bash
   bash management/common/install/language-tools/cargo-tools.sh
   # or npm-install-globals.sh, go-tools.sh, uv-tools.sh
   ```

4. **Verify installation**:

   ```bash
   which toolname
   toolname --version
   ```

## Adding a New Language Package Manager

If you need to add a new language package manager (e.g., gem, pip, dotnet):

1. **Create new script** named `{manager}-tools.sh`

2. **Follow the standard pattern**:
   - Source required libraries
   - Source language environment
   - Read packages from `packages.yml` via `parse-packages.py`
   - Loop through packages
   - Install with language package manager
   - Report failures via `output_failure_data()`

3. **Update parse-packages.py**:
   - Add new package type to argument parser
   - Add extraction function for new package type
   - Add to packages.yml schema

4. **Add packages to packages.yml**:

   ```yaml
   gem_packages:
     - name: package1
       description: "Description"
   ```

## Examples

### Cargo packages (cargo-tools.sh)

```bash
source "$HOME/.cargo/env"

print_banner "Installing Rust CLI Tools"

/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=cargo | while read -r package; do
  log_info "Installing $package..."
  if cargo binstall -y "$package"; then
    log_success "$package installed"
  else
    manual_steps="Install manually with cargo:
   cargo install $package

Or try cargo-binstall directly:
   cargo binstall -y $package"
    output_failure_data "$package" "https://crates.io/crates/$package" "latest" "$manual_steps" "Failed to install via cargo-binstall"
    log_warning "$package installation failed (see summary)"
  fi
done
```

### npm packages (npm-install-globals.sh)

```bash
source "$NVM_DIR/nvm.sh"

NPM_PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=npm)

for package in $NPM_PACKAGES; do
  if npm list -g "$package" --depth=0 &>/dev/null; then
    echo "  $package already installed (skipping)"
  else
    log_info "Installing $package..."
    if npm install -g "$package"; then
      log_success "$package installed"
    else
      manual_steps="Install manually with npm:
   npm install -g $package

View package on npm:
   https://www.npmjs.com/package/$package"
      output_failure_data "$package" "https://www.npmjs.com/package/$package" "latest" "$manual_steps" "Failed to install via npm"
      log_warning "$package installation failed (see summary)"
    fi
  fi
done
```

## Error Handling

Language tool installers handle errors by:

- Continuing to next package on individual failures
- Logging each failure via `output_failure_data()`
- Providing manual installation instructions specific to package manager
- Completing the loop to install as many packages as possible

**Note**: Current implementation doesn't exit with error code if some packages fail. This allows maximum installation but loses error signal. Consider tracking failure count and exiting with error if any fail.

## Important Notes

1. **Environment sourcing**: Always source the language environment before installing (nvm.sh, .cargo/env, etc.)

2. **Package manager availability**: Assumes language manager is already installed (via language-managers/)

3. **Idempotency**: npm checks if already installed, others rely on package manager's idempotency

4. **Failure resilience**: Loop continues on individual package failures

5. **Manual steps**: Provide both direct package manager command and package registry URL

## Common Issues

**Issue**: Package manager not found

- **Solution**: Ensure language manager installer has run first

**Issue**: Environment not sourced correctly

- **Solution**: Check that source path matches language manager installation

**Issue**: Some packages fail silently

- **Solution**: Check package name in packages.yml matches registry name

**Issue**: Network timeouts

- **Solution**: Retry failed packages, check network connectivity
