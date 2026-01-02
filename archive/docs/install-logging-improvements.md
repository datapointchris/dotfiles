# Installation Logging and Output Structure Improvements

**Created**: 2025-12-09
**Status**: ✅ COMPLETE - All 8 phases implemented and committed
**Context**: Analyzed wsl-install-log-failures.log from corporate restricted environment

## Executive Summary

The install.sh output suffers from:

1. **Inconsistent heading hierarchy** - mixed use of print_banner, print_header, print_section
2. **Missing critical details** - download URLs, extraction paths, installation locations not logged
3. **Incomplete error handling** - some failures have no manual instructions
4. **Redundant messaging** - scripts and main install.sh both printing status
5. **Poor failure summary formatting** - confusing structure, useless info (exit codes, timestamps)
6. **Spacing issues** - excessive whitespace from print_banner usage

**Solution**: Establish clear heading hierarchy, enhance logging detail, improve error messages, remove redundancy.

---

## Heading Hierarchy Design

### Hierarchy Rules

- **print_title** (h1) - Main install.sh only, top-level sections
- **print_header** (h2) - Main install.sh only, phase boundaries
- **print_section** (h3) - Individual installer scripts, specific tasks
- **log_*** - All detail logging within installers

### Current vs. Proposed

**Main install.sh**:

- ✅ KEEP: `print_title "Dotfiles Installation - $platform"`
- ✅ KEEP: `print_header "System Packages (apt)"`
- ✅ KEEP: `print_header "Coding Fonts"`
- ✅ KEEP: `print_header "Go Toolchain"`
- ✅ KEEP: `print_header "GitHub Release Tools"`
- ✅ KEEP: `print_header "Custom Distribution Tools"`
- ✅ KEEP: `print_header "Rust/Cargo Tools"`
- ✅ KEEP: `print_header "Language Package Managers"`
- ✅ KEEP: `print_header "Shell Plugins"`
- ✅ KEEP: `print_header "Custom Go Applications"`
- ✅ KEEP: `print_header "Symlinking Dotfiles"`
- ✅ KEEP: `print_header "Theme System"`
- ✅ KEEP: `print_header "Tmux Plugins"`
- ✅ KEEP: `print_header "Neovim Plugins"`
- ❌ REMOVE: `print_section "Configuring ZSH as default shell"` → Change to `print_header`
- ✅ KEEP: `print_header "Installation Summary"` (but rename to "Error Summary")

**Individual installer scripts**:

- ❌ REMOVE ALL: `print_banner` (23 scripts use this)
- ✅ KEEP: `print_section "Installing $font_name"` in font scripts
- ✅ KEEP: `print_section "Installing shell plugins"` in shell-plugins.sh

---

## Issue-by-Issue Analysis and Solutions

### 1. Font Installers - Missing Download URL

**Issue**: Log shows "Downloading JetBrains Mono Nerd Font..." but not the actual URL being downloaded from.

**Root Cause**: `download_nerd_font()` in `font-installer.sh:47` uses hardcoded URL but doesn't log it.

```bash
curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz"
```

**Solution**:

```bash
# In font-installer.sh download_nerd_font()
local url="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz"
log_info "Downloading from: $url"
if ! curl -fsSL "$url" -o "${package}.tar.xz"; then
```

**Applies to**: All Nerd Font installers (13 scripts)

---

### 2. Font Installers - Incomplete Manual Instructions

**Issue**: Instructions say "Move to: /tmp/fonts-JetBrainsMonoNerdFont" but don't explain what to do after that.

**Current (font-installer.sh:48-50)**:

```bash
manual_steps="Download manually: https://github.com/ryanoasis/nerd-fonts/releases/latest
Extract: tar -xf ${package}.tar.xz
Move to: $download_dir"
```

**Problem**: $download_dir is /tmp/ which is ephemeral. User needs to know:

1. Where is the final install location?
2. How to install the fonts once they're extracted?

**Solution**:

```bash
manual_steps="1. Download manually:
   https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${package}.tar.xz

2. Extract the archive:
   tar -xf ${package}.tar.xz

3. Copy font files to system font directory:
   cp *NerdFont*.${extension} ${system_font_dir}/

4. Refresh font cache (Linux only):
   fc-cache -fv

5. Verify installation:
   fc-list | grep -i ${package}"
```

**Requires**: Pass $system_font_dir to download_nerd_font() function

**Applies to**: All Nerd Font installers (13 scripts)

---

### 3. Fira Code - Better Instructions But Needs Spacing

**Issue**: Instructions look good but need blank line before "Download manually from GitHub:"

**Current (firacode.sh:26-32)**:

```bash
manual_steps="Download manually from GitHub:
   https://github.com/tonsky/FiraCode/releases/latest

Extract and install:
   unzip Fira_Code_v6.2.zip
   mkdir -p $system_font_dir
   cp ttf/*.ttf $system_font_dir/"
```

**Solution**:

```bash
manual_steps="
Download manually from GitHub:
   https://github.com/tonsky/FiraCode/releases/latest
   (File: Fira_Code_v6.2.zip)

Extract and install:
   unzip Fira_Code_v6.2.zip
   mkdir -p $system_font_dir
   cp ttf/*.ttf $system_font_dir/

Refresh font cache (Linux only):
   fc-cache -fv

Verify installation:
   fc-list | grep -i 'Fira Code'"
```

**Applies to**: firacode.sh, commitmono.sh, intelone.sh, iosevka-base.sh

---

### 4. SGr-Iosevka - No Download or Install Instructions

**Issue**: Failure shows only "Download failed" with no manual instructions.

**Investigation Required**: Need to read sgr-iosevka.sh to see what's missing.

**Expected Solution**: Add proper manual_steps with:

1. Exact download URL
2. Extraction commands
3. Installation commands
4. Verification steps

---

### 5. FiraCodeiScript - Confusing Messages

**Issue**:

```yaml
Download manually from GitHub:
   https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Regular.ttf

Or browse the repository:
   https://github.com/kencrocken/FiraCodeiScript

Save files to:
   /mnt/c/Windows/Fonts/
```

**Problems**:

- "Or browse the repository" is confusing - it's a direct file download, not browsing
- "Save files to" is vague - should say "Copy to" or "Install to"
- Should include refresh and verify steps

**Solution**:

```bash
manual_steps="
1. Download the font file:
   curl -fsSL https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Regular.ttf -o FiraCodeiScript-Regular.ttf

   Or download in browser:
   https://github.com/kencrocken/FiraCodeiScript/raw/master/FiraCodeiScript-Regular.ttf

2. Install to system fonts:
   cp FiraCodeiScript-Regular.ttf $system_font_dir/

3. Refresh font cache (Linux only):
   fc-cache -fv

4. Verify installation:
   fc-list | grep -i 'FiraCodeiScript'"
```

**Applies to**: firacodescript.sh

---

### 6. Comic Mono - Needs More Details

**Issue**: Log shows:

```text
[INFO] ● Downloading Comic Mono...
[INFO] ✓ Downloaded 2 files
[INFO] ● Pruning unwanted variants...
[INFO] ✓ Pruned 0 files (kept 2)
[INFO] ● Standardizing filenames...
[INFO] ● Installing to system fonts directory...
[INFO] ● Refreshing font cache...
[INFO] ✓ Comic Mono installation complete
```

**User Wants**:

1. What URL did it download from?
2. What variants were pruned? (in this case, none)
3. Filename standardized from what to what?
4. Which system font directory?
5. How is it refreshing the font cache (command)?
6. Did the copy actually succeed? (User says fonts not in /mnt/c/Windows/Fonts)

**Solution**:

**In comicmono.sh download_comicmono()**:

```bash
local base_url="https://dtinth.github.io/comic-mono-font"
local files=("ComicMono.ttf" "ComicMono-Bold.ttf")

for file in "${files[@]}"; do
  log_info "Downloading: ${base_url}/${file}"
  if ! curl -fsSL "$base_url/$file" -o "$download_dir/$file"; then
```

**In font-installer.sh prune_font_family()**:

```bash
# Add before deletion
log_info "Pruning variants: ExtraLight, Light, Thin, Medium, SemiBold, ExtraBold, Black, Retina, Propo"

# After deletion
if [[ $pruned -gt 0 ]]; then
  log_success "Pruned $pruned files (kept $after)"
else
  log_info "No pruning needed (kept $after files)"
fi
```

**In font-installer.sh standardize_font_family()**:

```bash
# Current: silent
# Add logging:
find "$font_dir" -type f -name "* *" 2>/dev/null | while read -r file; do
  local newname="${file// /-}"
  log_info "Standardizing: $(basename "$file") → $(basename "$newname")"
  mv "$file" "$newname"
done

# After loop
if [[ $files_with_spaces -eq 0 ]]; then
  log_info "No filename standardization needed"
else
  log_success "Standardized $files_with_spaces filenames"
fi
```

**In font-installer.sh install_font_files()**:

```bash
# Add at start:
log_info "Installing to: $target_dir"

# After copy:
local installed_count
installed_count=$(find "$target_dir" -type f \( -name "*.ttf" -o -name "*.otf" -o -name "*.ttc" \) -newer "$temp_marker" 2>/dev/null | wc -l | tr -d ' ')
rm -f "$temp_marker"

if [[ $installed_count -eq 0 ]]; then
  log_error "Copy failed - no files found in $target_dir"
  return 1
fi

log_success "Installed $installed_count font files to: $target_dir"
```

**In font-installer.sh refresh_font_cache()**:

```bash
# Current: silent
# Add logging:
case "$platform" in
  macos)
    log_info "Font cache refresh not needed on macOS (automatic)"
    ;;
  wsl)
    log_info "Font cache refresh: Windows manages font cache automatically"
    log_info "You may need to restart applications to see new fonts"
    ;;
  linux|arch)
    log_info "Refreshing font cache: fc-cache -fv"
    if fc-cache -fv 2>&1 | grep -q "succeeded"; then
      log_success "Font cache refreshed successfully"
    fi
    ;;
esac
```

**Applies to**: All font installers using font-installer.sh library

---

### 7. GitHub Release Tools - Confusing Messages

**Issue**: Log shows:

```text
[INFO] ● Latest version: v25.5.31
[INFO] ● Latest version: v25.5.31
[INFO] ● Downloading yazi...
```

And for already-installed tools:

```text
[INFO] ● Latest version: v2.1.1
[INFO] ● Downloading glow...
[INFO] ● Extracting...
[INFO] ● Installing to ~/.local/bin...
[INFO] ✓ glow installed successfully
```

**Root Cause 1**: yazi.sh:29 and yazi.sh:46 both call `log_info "Latest version: $VERSION"`

**Root Cause 2**: GitHub release installers don't have proper idempotency checks before logging "Downloading..."

**Solution for yazi.sh**:

```bash
# Remove duplicate at line 46
# Keep only line 29
```

**Solution for all GitHub release installers**:

**In github-release-installer.sh should_skip_install()**:

```bash
# Current line 63:
log_success "$binary_name already installed, skipping"

# Change to:
log_success "$binary_name already installed (skipping download/installation)"
```

**In individual installers (glow.sh, duf.sh, etc.)**:

```bash
# After should_skip_install() check, before download
if [[ "$SKIP_INSTALL" == "false" ]]; then
  log_info "Downloading from: $DOWNLOAD_URL"
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_ARCHIVE"; then
```

**Applies to**: All 11 GitHub release tool installers

---

### 8. GitHub Release Tools - Need More Path Details

**Issue**: User wants to see:

- Where downloading from (URL)
- Where extracting to (path)
- Where installing to exactly (path)

**Solution**:

**In github-release-installer.sh install_from_tarball()**:

```bash
# Add at start:
log_info "Download URL: $download_url"
log_info "Extraction directory: $extract_dir"
log_info "Installation target: $target_path"

# After extraction:
log_success "Extracted to: $extract_dir"

# After installation:
log_success "Installed to: $target_path"
```

**In github-release-installer.sh install_from_zip()**:

```bash
# Same pattern as install_from_tarball
```

**Applies to**: All GitHub release installers using the library

---

### 9. Claude Code - Confusing Output Mix

**Issue**:

```text
═══════════════════════════════════════════
Installing Claude Code
═══════════════════════════════════════════

[INFO] ● Latest version: 2.0.62
[INFO] ● Installing via official installer...
[INFO] ✓ Claude Code installed successfully
[INFO] ✓ Verified: 2.0.62 (Claude Code)
═══════════════════════════════════════════
✅ Claude Code installation complete
═══════════════════════════════════════════

[INFO] ✓ claude-code installed
```

**Problems**:

- Banner bars used in individual script (should be print_section)
- "Claude Code installation complete" in banner (redundant)
- Final [INFO] from run_installer is redundant

**Solution**:

**In claude-code.sh**:

```bash
# REMOVE print_banner "Installing Claude Code"
# CHANGE TO:
print_section "Installing Claude Code"

# REMOVE final banner:
# print_banner "✅ Claude Code installation complete"
# KEEP ONLY:
log_success "Claude Code installed successfully"
log_success "Verified: $installed_version (Claude Code)"
```

**Result**:

```text
Installing Claude Code
──────────────────────────────────────────
[INFO] ● Latest version: 2.0.62
[INFO] ● Installing via official installer...
[INFO] ✓ Claude Code installed successfully
[INFO] ✓ Verified: 2.0.62 (Claude Code)
[INFO] ✓ claude-code installed
```

**Applies to**: All custom installer scripts using print_banner

---

### 10. tenv Failed - No Manual Instructions

**Issue**:

```yaml
[INFO] ● Latest version: v4.9.0
[INFO] ● Downloading tenv...
[WARNING] ▲ tenv installation failed (see /tmp/dotfiles-install-failures-20251209-092234.txt)
curl: (60) SSL certificate problem: unable to get local issuer certificate
...
/home/chris/dotfiles/management/common/install/github-releases/tenv.sh: line 68: ARCH: unbound variable
```

**Root Cause**: Script has a bug (unbound variable ARCH) and doesn't call output_failure_data()

**Investigation Required**: Need to read tenv.sh to see the failure handling.

**Expected Solution**:

1. Fix ARCH variable issue
2. Add proper output_failure_data() call with manual steps

---

### 11. Shell Plugins - Excessive Spacing

**Issue**: Log shows:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Shell Plugins
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Installing shell plugins
───────────────────────────────────────
```

**Root Cause**: print_header adds spacing after, print_section adds spacing before, resulting in double spacing.

**Solution**: Remove print_section from shell-plugins.sh since main install.sh already has print_header.

**In shell-plugins.sh**:

```bash
# REMOVE: print_section "Installing shell plugins" "cyan"
# Script should start directly with logging:
log_info "Installing shell plugins to: $PLUGINS_DIR"
```

**Applies to**: Any installer script that has print_section when main install.sh already has print_header for that phase

---

### 12. Shell Plugins - Want Individual Install Paths

**Issue**: Log shows:

```text
[INFO] ● git-open already installed
[INFO] ● zsh-vi-mode already installed
```

User wants to see WHERE they're installed.

**Solution**:

**In shell-plugins.sh**:

```bash
while IFS='|' read -r name repo; do
  PLUGIN_DIR="$PLUGINS_DIR/$name"

  if [[ -d "$PLUGIN_DIR" ]]; then
    log_success "$name already installed: $PLUGIN_DIR"
  else
    log_info "Installing $name to: $PLUGIN_DIR"
    log_info "Repository: $repo"
    if git clone "$repo" "$PLUGIN_DIR" --quiet; then
      log_success "$name installed: $PLUGIN_DIR"
```

**Result**:

```text
[INFO] ✓ git-open already installed: /home/chris/.config/zsh/plugins/git-open
[INFO] ● Installing zsh-vi-mode to: /home/chris/.config/zsh/plugins/zsh-vi-mode
[INFO] ● Repository: https://github.com/jeffreytse/zsh-vi-mode
[INFO] ✓ zsh-vi-mode installed: /home/chris/.config/zsh/plugins/zsh-vi-mode
```

**Applies to**: shell-plugins.sh

---

### 13. Shell Plugins - Repeated Message

**Issue**: Log shows:

```text
[INFO] ✓ Shell plugins installed to /home/chris/.config/zsh/plugins
[INFO] ✓ shell-plugins installed
```

**Root Cause**:

- Line 1: shell-plugins.sh:50
- Line 2: run_installer() in orchestration/run-installer.sh:16

**Solution**: Remove redundant log from shell-plugins.sh since run_installer() handles success logging.

**In shell-plugins.sh**:

```bash
# REMOVE: log_success "Shell plugins installed to $PLUGINS_DIR"
# Let run_installer() handle the final success message
```

**Applies to**: All installer scripts - audit for redundant success logging

---

### 14. Custom Go Applications - Messy Output

**Issue**: Log shows raw task command output mixed with echo statements:

```yaml
task: [clean] echo "Cleaning..."
Cleaning...
task: [clean] rm -f ./sess
task: [build] echo "Building sess..."
Building sess...
```

**Root Cause**: Main install.sh lines 128-129 call task directly, showing all task output.

**Solution Option 1 - Suppress Task Output**:

```bash
print_header "Custom Go Applications" $header_color

log_info "Building sess..."
cd "$DOTFILES_DIR/apps/common/sess" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean install > /dev/null 2>&1
if [[ -f "$HOME/go/bin/sess" ]]; then
  log_success "sess installed: $HOME/go/bin/sess"
else
  log_error "sess build failed"
fi

log_info "Building toolbox..."
cd "$DOTFILES_DIR/apps/common/toolbox" && PATH="$HOME/go/bin:/usr/local/go/bin:$PATH" task clean install > /dev/null 2>&1
if [[ -f "$HOME/go/bin/toolbox" ]]; then
  log_success "toolbox installed: $HOME/go/bin/toolbox"
else
  log_error "toolbox build failed"
fi
```

**Solution Option 2 - Create Wrapper Scripts**:
Create `management/common/install/custom-apps/sess.sh` and `toolbox.sh` that:

1. Use print_section for heading
2. Call task with suppressed output
3. Use log_* for status messages
4. Add proper failure handling with output_failure_data()

**Recommended**: Option 2 (consistency with other installers, proper error handling)

**Applies to**: Custom Go application builds in install.sh

---

### 15. Theme System - Unclear What's Happening

**Issue**: Log shows:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Theme System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

tinted-shell already installed
schemes already installed
tinted-shell already installed
schemes already installed
tinted-shell up to date
schemes up to date
```

**Root Cause**: install.sh:134-136 directly calls tinty commands with no logging context.

**Solution**: Create `management/common/install/plugins/tinty-themes.sh` wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_section "Installing Tinty Theme System"

if ! command -v tinty >/dev/null 2>&1; then
  log_error "tinty not found - install tinty first"
  exit 1
fi

log_info "Installing theme repositories..."
source "$HOME/.cargo/env"

log_info "Running: tinty install"
if tinty install 2>&1 | while read -r line; do
  [[ "$line" =~ "already installed" ]] && log_success "$line" && continue
  [[ "$line" =~ "installed" ]] && log_success "$line" && continue
  log_info "$line"
done; then
  log_success "Theme repositories installed"
else
  log_warning "tinty install encountered issues"
fi

log_info "Syncing current theme..."
log_info "Running: tinty sync"
if tinty sync 2>&1 | while read -r line; do
  [[ "$line" =~ "up to date" ]] && log_success "$line" && continue
  log_info "$line"
done; then
  log_success "Theme sync complete"
else
  log_warning "tinty sync encountered issues"
fi
```

**In install.sh**:

```bash
print_header "Theme System" $header_color
run_installer "$plugins/tinty-themes.sh" "tinty-themes"
```

**Applies to**: Theme system installation (install.sh:134-136)

---

### 16. Tmux Plugins - Want Install Location

**Issue**: Log shows:

```text
[INFO] ✓ TPM already installed
[INFO] ✓ tpm installed
[INFO] ● Installing tmux plugins...
Already installed "tpm"
Already installed "tmux-fzf"
```

User wants to know WHERE plugins are installed.

**Solution**:

**In tpm.sh** (need to read this file first):

```bash
log_success "TPM installed: $TPM_DIR"
```

**In tmux-plugins.sh**:

```bash
log_info "Installing tmux plugins to: $HOME/.config/tmux/plugins/"

# Parse TPM output to extract plugin paths:
if "$TPM_DIR/bin/install_plugins" 2>&1 | while read -r line; do
  if [[ "$line" =~ "Already installed" ]]; then
    plugin_name=$(echo "$line" | sed 's/Already installed "\(.*\)"/\1/')
    log_success "$plugin_name already installed: $HOME/.config/tmux/plugins/$plugin_name"
  elif [[ "$line" =~ "Installing" ]]; then
    plugin_name=$(echo "$line" | sed 's/Installing "\(.*\)"/\1/')
    log_info "Installing $plugin_name..."
  fi
done; then
  log_success "Tmux plugins installed"
```

**Applies to**: tpm.sh, tmux-plugins.sh

---

### 17. Tmux Plugins - Repeated Messages

**Issue**: Messages appear twice - once from script, once from run_installer().

**Root Cause**: Same as issue #13 - redundant logging.

**Solution**: Remove redundant logging from tmux-plugins.sh, let run_installer() handle final message.

---

### 18. Neovim Plugins - Double Banner

**Issue**: Log shows:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Neovim Plugins
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════════════════════════════════════════
Installing Neovim Plugins
═══════════════════════════════════════════
```

**Root Cause**:

- Line 1: install.sh:142 `print_header "Neovim Plugins"`
- Line 2: nvim-plugins.sh:10 `print_banner "Installing Neovim Plugins"`

**Solution**:

**In nvim-plugins.sh**:

```bash
# REMOVE: print_banner "Installing Neovim Plugins"
# Script should start directly with:
log_info "Installing Neovim plugins via Lazy.nvim..."
```

**Applies to**: nvim-plugins.sh

---

### 19. Neovim Error - Failed to Get Terminal Size

**Issue**:

```bash
Error detected while processing command line:
Failed to run `config` for image.nvim

...ocal/share/nvim/lazy/image.nvim/lua/image/utils/term.lua:34: Failed to get terminal size
```

**Root Cause**: Windows Terminal running WSL - image.nvim can't get terminal dimensions in headless mode.

**Research Required**:

1. Is this a known issue with image.nvim in WSL?
2. Can we suppress this error or configure image.nvim differently?
3. Should we skip image.nvim in WSL environments?

**Potential Solutions**:

1. Add TERM=dumb or TERM=xterm-256color before nvim headless call
2. Disable image.nvim in WSL via lazy.nvim cond function
3. Add --clean flag to skip user config (but we want to test actual config)
4. Suppress stderr for known non-critical errors

**Investigation Needed**: Test different approaches, check image.nvim GitHub issues.

---

### 20-24. Installation Summary - Multiple Issues

**Issues**:

1. Should be "Error Summary" or "Failure Summary" (red/yellow header)
2. Use print_section_error instead of manual equals borders
3. "Version: latest" is useless information
4. "Exit Code: 1" is confusing for users
5. Want: script, download URL, failed reason, manual steps (no timestamp)

**Current Code (run-installer.sh:46-62)**:

```bash
cat >> "$FAILURES_LOG" << EOF
========================================
$failure_tool - Installation Failed
========================================
Script: $script
Exit Code: $exit_code
Timestamp: $(date -Iseconds)
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}
${failure_reason:+Reason: $failure_reason}

${failure_manual:+Manual Installation Steps:
$failure_manual
}
---
EOF
```

**Solution 1 - Improve Failure Log Format**:

**In run-installer.sh**:

```bash
# Improved format:
cat >> "$FAILURES_LOG" << EOF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$failure_tool - Installation Failed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Installer: $(basename "$script")
${failure_reason:+Error: $failure_reason}
${failure_url:+Download URL: $failure_url}
${failure_version:+$([ "$failure_version" != "latest" ] && echo "Version: $failure_version")}

${failure_manual:+How to Install Manually:
$failure_manual
}

EOF
```

**Solution 2 - Change Summary Header**:

**In install.sh show_failures_summary()**:

```bash
# Line 36: Change from
print_header "Installation Summary" "$header_color"
# To:
print_header "⚠️  Installation Failures" "red"
```

**Solution 3 - Filter Out Useless Fields**:

**In output_failure_data()** (failure-logging.sh - need to read this):

- Don't output VERSION if it's "latest"
- Don't output TIMESTAMP (already in log filename)
- Don't output EXIT_CODE (not useful to user)

**Applies to**: run-installer.sh, failure-logging.sh, install.sh

---

### 25. Confusing ZSH Configuration After Failure Summary

**Issue**: After showing all failures, suddenly:

```text
Configuring ZSH as default shell
──────────────────────────────────
```

**Problem**: Creates impression that install is continuing successfully when it actually had failures.

**Solution**: Move `configure_zsh_default_shell()` to run BEFORE `show_failures_summary()`.

**In install.sh**:

```bash
# Current order (lines 143-145):
run_installer "$plugins/nvim-plugins.sh" "nvim-plugins"

show_failures_summary()

# In wsl/arch case blocks (lines 257-258, 266-267):
print_section "Configuring ZSH as default shell" $section_color
configure_zsh_default_shell

# CHANGE TO:
run_installer "$plugins/nvim-plugins.sh" "nvim-plugins"

print_section "Configuring ZSH as default shell" $section_color
configure_zsh_default_shell

show_failures_summary()
```

**Alternative**: Add clear "Post-Installation Configuration" header:

```bash
run_installer "$plugins/nvim-plugins.sh" "nvim-plugins"

print_header "Post-Installation Configuration" $header_color
print_section "Configuring ZSH as default shell" $section_color
configure_zsh_default_shell

show_failures_summary()
```

**Recommended**: Alternative (clearer structure)

**Applies to**: install.sh

---

## Cross-Cutting Solutions

### Solution 1: Remove All print_banner from management/

**Scope**: 23 files use print_banner

**Commands**:

```bash
# Find all uses:
grep -r "print_banner" management/ --include="*.sh"

# Files to modify:
management/common/install/github-releases/yazi.sh (2 instances)
management/common/install/github-releases/lazygit.sh
management/common/install/github-releases/neovim.sh
management/common/install/github-releases/fzf.sh
management/common/install/language-tools/cargo-tools.sh
management/common/install/language-tools/go-tools.sh
management/common/install/language-tools/uv-tools.sh
management/common/install/language-managers/go.sh
management/common/install/language-managers/rust.sh
management/common/install/language-managers/uv.sh
management/common/install/language-managers/nvm.sh
management/common/install/custom-installers/claude-code.sh (2 instances)
management/common/install/custom-installers/bats.sh
management/common/install/custom-installers/awscli.sh
management/common/install/custom-installers/terraform-ls.sh
management/common/install/plugins/nvim-plugins.sh
management/common/install/plugins/tpm.sh
# ... (verify complete list with grep)
```

**Replacement Strategy**:

1. If script has print_banner as ONLY heading → Remove entirely (parent has print_header)
2. If script has print_banner for sub-tasks → Change to print_section

**Examples**:

**Type 1 - Remove Entirely**:

```bash
# nvim-plugins.sh
# BEFORE:
print_banner "Installing Neovim Plugins"
log_info "Installing Neovim plugins via Lazy.nvim..."

# AFTER:
log_info "Installing Neovim plugins via Lazy.nvim..."
```

**Type 2 - Change to print_section**:

```bash
# yazi.sh (has multiple sub-sections)
# BEFORE:
print_banner "Installing Yazi"

# AFTER:
print_section "Installing Yazi"
```

### Solution 2: Enhance Library Logging

**font-installer.sh changes**:

1. download_nerd_font() - Log URL, extraction details
2. prune_font_family() - Log what's being pruned, results
3. standardize_font_family() - Log standardization details
4. install_font_files() - Log target directory, verify copy success, log count
5. refresh_font_cache() - Log command being run, results

**github-release-installer.sh changes**:

1. install_from_tarball() - Log download URL, extraction dir, install path
2. install_from_zip() - Same as tarball
3. should_skip_install() - Clarify message (add "skipping download/installation")

### Solution 3: Audit and Remove Redundant Success Logging

**Pattern to find**:

```bash
# Installer script ends with:
log_success "Tool X installed"

# run_installer.sh also logs:
log_success "$tool_name installed"

# Result: duplicate messages
```

**Solution**: Remove final success log from installer scripts, let run_installer() handle it.

**Exceptions**: Keep detailed success logging (with paths) inside scripts, remove generic success log.

**Example**:

```bash
# GOOD (keep):
log_success "sess installed: $HOME/go/bin/sess"
# Let run_installer add: log_success "sess installed"

# BAD (remove):
log_success "Shell plugins installed"
# Duplicate of run_installer: log_success "shell-plugins installed"
```

### Solution 4: Create Missing Wrapper Scripts

**Need wrappers for**:

1. `management/common/install/custom-apps/sess.sh`
2. `management/common/install/custom-apps/toolbox.sh`
3. `management/common/install/plugins/tinty-themes.sh`

**Template**:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_section "Installing <Tool Name>"

# Tool-specific installation logic
# Use log_info, log_success, log_error
# Call output_failure_data() on failure
```

---

## Implementation Plan

### Phase 1: Heading Hierarchy (Quick Wins) ✅ COMPLETE

1. ✅ Remove all print_banner from management/ scripts (23 files)
   - Verified: 0 instances remaining in management/
2. ✅ Change install.sh "Installation Summary" to error variant
   - Now uses: `print_header_error "Installation Failures"`
3. ✅ Remove redundant print_section where parent has print_header
   - Verified: shell-plugins.sh, nvim-plugins.sh, claude-code.sh all cleaned

**Completed**: 2025-12-09 (33 files modified via global color standardization commit)

**Bonus completed from Phase 8:**

- ✅ ZSH configuration now under "Post-Installation Configuration" header (addresses Phase 8 concern)

### Phase 2: Library Enhancements (Medium Effort) ✅ COMPLETE

1. ✅ Enhance font-installer.sh logging (5 functions)
   - download_nerd_font(): Log download URL before downloading
   - prune_font_family(): Log what's being pruned, better messaging if nothing pruned
   - standardize_font_family(): Log filename changes (from → to), better messaging
   - install_font_files(): Log target directory, verify copy success, include paths in success messages
   - refresh_font_cache(): Log platform-specific cache refresh commands and results

2. ✅ Enhance github-release-installer.sh logging (3 functions)
   - should_skip_install(): Clarify message "(skipping download/installation)"
   - install_from_tarball(): Log download URL, extraction dir, installation target
   - install_from_zip(): Log download URL, extraction dir, installation target

3. ✅ Update failure message formatting in run-installer.sh
   - Use print_section_error for consistent formatting (automatic ❌ emoji + red color)
   - Removed hardcoded separators in favor of formatting library
   - Removed useless fields: Exit Code, Timestamp
   - Filter "Version: latest" (only show if actual version)
   - Better field labels: "Installer:" instead of "Script:", "Error:" instead of "Reason:"
   - Changed "Manual Installation Steps:" to "How to Install Manually:"

**Completed**: 2025-12-09 (3 library files enhanced)

### Phase 3: Font Installer Improvements (Moderate) ✅ COMPLETE

1. ✅ Enhanced download_nerd_font() library function:
   - Added system_font_dir as 4th parameter
   - Replaced incomplete manual instructions with complete 5-step guide (download URL, extraction, installation, cache refresh, verification)

2. ✅ Updated 13 Nerd Font installer scripts to pass system_font_dir parameter:
   - 3270.sh, cascadia.sh, droid.sh, hack.sh, iosevka.sh, jetbrains.sh, meslo.sh, monaspace.sh, robotomono.sh, seriousshanns.sh, sourcecode.sh, spacemono.sh, terminess.sh

3. ✅ Fixed sgr-iosevka.sh manual instructions:
   - Defined complete manual_steps variable at function start
   - Applied to all 4 download failure points (previously just "Download failed")

4. ✅ Fixed firacodescript.sh manual instructions:
   - Replaced confusing messages with clear 4-step guide
   - Added explicit curl commands, installation path, cache refresh, verification

**Completed**: 2025-12-09 (16 files modified: 1 library + 13 Nerd Font installers + 2 specific fonts)

### Phase 4: GitHub Release Improvements (Moderate) ✅ COMPLETE

1. ✅ Fixed duplicate version logging:
   - yazi.sh: Removed duplicate "Latest version" log
   - terraformer.sh: Removed duplicate "Latest version" log

2. ✅ Added download URL logging to custom installers:
   - yazi.sh, neovim.sh, terraformer.sh, tenv.sh
   - Note: Scripts using github-release-installer.sh library (8 scripts) already have URL logging from Phase 2

3. ✅ Removed redundant success logging:
   - terraformer.sh: Removed generic "installed successfully" message
   - Kept detail-rich success logs (neovim version, yazi+ya binaries, tenv proxy binaries)

**Completed**: 2025-12-09 (4 files modified)

### Phase 5: Plugin Installation Improvements (Moderate) ✅ COMPLETE

1. ✅ Created tinty-themes.sh wrapper
   - Wraps tinty install/sync commands with proper logging
   - Parses tinty output to show progress messages
   - Adds error handling with manual installation instructions

2. ✅ Enhanced shell-plugins.sh with path logging
   - Log full plugin paths for "already installed" and "newly installed" cases
   - Added repository URL logging during installation
   - Removed redundant final success message (run_installer handles this)

3. ✅ Enhanced tmux-plugins.sh with path logging
   - Log target directory at start
   - Parse TPM output to show individual plugin installation paths
   - Use PIPESTATUS to check TPM exit code when piping through while loop

4. ✅ nvim-plugins.sh already clean (no double banner)
   - Verified no print_banner exists (cleaned in Phase 1)
   - Script starts directly with log_info

**Completed**: 2025-12-10 (4 files modified: 3 enhanced + 1 new wrapper)

### Phase 6: Custom App Improvements (Moderate) ✅ COMPLETE

1. ✅ Created sess.sh wrapper
   - Wraps `task clean install` for sess binary
   - Suppresses verbose task output
   - Logs source directory, output directory, installation path, version
   - Checks for Go availability before building
   - Provides manual build instructions on failure

2. ✅ Created toolbox.sh wrapper
   - Same pattern as sess.sh but for toolbox binary
   - Comprehensive error handling with manual steps

3. ✅ Updated install.sh to use wrappers
   - Added `custom_apps` variable alongside other installer paths
   - Replaced direct `task clean && task install` calls with `run_installer` pattern
   - Now consistent with all other installer scripts

**Completed**: 2025-12-10 (3 files modified: 1 enhanced + 2 new wrappers)

### Phase 7: Error Handling Improvements (Moderate) ✅ COMPLETE

1. ✅ Fixed tenv.sh ARCH variable bug
   - Changed `${ARCH}` to `${RAW_ARCH}` in manual installation instructions
   - Script defines RAW_ARCH but was incorrectly referencing ARCH
   - Caused "unbound variable" error with `set -u` when download failed

2. ✅ Manual instructions already comprehensive
   - Phase 3 addressed all font installer manual instructions
   - All installers using libraries have proper manual steps
   - No gaps found in manual instruction coverage

3. ✅ Failure log format already improved (Phase 2)
   - Filters "latest" version (only shows actual version numbers)
   - Uses print_section_error for consistent error styling
   - Shows "Installer:" and "Error:" labels
   - Removed EXIT_CODE and TIMESTAMP fields
   - Changed "Manual Installation Steps:" to "How to Install Manually:"

4. ✅ Fixed neovim image.nvim terminal size error
   - Added headless mode detection to image.nvim plugin condition
   - Changed from `cond = not vim.g.vscode` to `cond = not vim.g.vscode and #vim.api.nvim_list_uis() > 0`
   - Prevents "Failed to get terminal size" errors during plugin installation
   - Works on both macOS and WSL (headless mode universal issue, not platform-specific)

**Completed**: 2025-12-10 (2 files modified: tenv.sh, molten.lua)

### Phase 8: Structural Improvements (Quick) ✅ COMPLETE

1. ✅ Moved failure summary to end of installation
   - Removed `show_failures_summary()` call from end of `install_common_phases()`
   - Added `show_failures_summary()` after ZSH configuration in each platform case
   - macOS: After `install_common_phases` (no ZSH config on macOS)
   - WSL: After `configure_zsh_default_shell`
   - Arch: After `configure_zsh_default_shell`
   - Result: Failure summary now appears at the very end, not interrupting the installation flow

2. ✅ Audited and removed all redundant success logging
   - Removed "installation complete" logs from 21 font installers
   - Removed "Tmux plugins installed" from tmux-plugins.sh
   - Removed "Theme sync complete" from tinty-themes.sh
   - Removed "Neovim plugins installed" from nvim-plugins.sh
   - Kept detail-rich success logs (with paths, versions, progress info)
   - Result: No duplicate success messages, cleaner output

**Completed**: 2025-12-10 (25 files modified: 1 install.sh + 21 fonts + 3 plugin scripts)

---

## Testing Strategy

### Unit Testing

- Each library change tested with individual scripts
- Verify logging appears correctly in output
- Verify failure cases still produce proper error messages

### Integration Testing

1. Run full install.sh on clean WSL system
2. Run with SKIP_FONTS=1 to test partial install
3. Run with failed network to test all failure paths
4. Verify log output matches expectations:
   - No duplicate messages
   - Clear hierarchy (title > header > section > log)
   - All URLs, paths logged
   - Manual instructions complete

### Validation Checklist

- [ ] No print_banner in any management/ script
- [ ] All font failures have complete manual instructions
- [ ] All GitHub release tools log download URLs
- [ ] All plugin installations log paths
- [ ] No duplicate success messages
- [ ] Failure summary uses proper format
- [ ] ZSH configuration before failure summary
- [ ] Theme system output is clear
- [ ] Go app builds have clean output
- [ ] Neovim image.nvim error handled

---

## Open Questions

### Question 1: Neovim image.nvim Error

**Context**: Windows Terminal + WSL causes "Failed to get terminal size" error

**Options**:

1. Set TERM=xterm-256color before nvim call
2. Conditionally disable image.nvim in WSL
3. Suppress known non-critical errors
4. Add fallback size in image.nvim config

**Decision Needed**: Test each option, choose most reliable

### Question 2: Font Installation Verification

**Context**: User reports fonts not in /mnt/c/Windows/Fonts despite "installed" message

**Investigation Required**:

1. Does `install_font_files()` have proper error handling for WSL?
2. Does WSL require elevated permissions for /mnt/c/Windows/Fonts?
3. Should we verify font installation with `fc-list` on Linux, directory check on WSL?

**Decision Needed**: Add verification step before claiming success

### Question 3: Comic Mono Silent Copy Failure

**Context**: Log says "Comic Mono installation complete" but files not in target directory

**Root Cause**: Likely `install_font_files()` doesn't check copy result on WSL

**Solution**: Add verification in install_font_files() (already in Phase 2)

### Question 4: Tinty Output Parsing

**Context**: tinty install/sync output is irregular

**Options**:

1. Parse line-by-line with pattern matching
2. Suppress all output, just check exit code
3. Capture and analyze at end

**Decision Needed**: Test tinty output format, choose parsing strategy

---

## Success Metrics

### Quantitative

- [x] 0 instances of print_banner in management/ ✅ Phase 1
- [ ] 100% of failures have manual instructions
- [ ] 100% of downloads log URL
- [ ] 0 duplicate success messages
- [ ] All path operations log target directories

### Qualitative

- [x] Log has clear visual hierarchy (title → header → section → detail) ✅ Phase 1
- [ ] User can reproduce any failed installation from manual instructions
- [ ] No confusion about what's installed where
- [x] Failure summary is scannable and actionable ✅ Phase 1 (uses error variant)
- [ ] Log file size reduced by ~20% (less redundancy)

---

## Files Requiring Changes

### Immediate Priority (Phase 1) ✅ COMPLETE

- [x] install.sh (heading changes, ZSH reorder)
- [x] 23 scripts using print_banner (remove/replace)

### High Priority (Phases 2-3)

- [x] management/common/lib/font-installer.sh ✅ Phase 2
- [x] management/common/lib/github-release-installer.sh ✅ Phase 2
- [x] management/orchestration/run-installer.sh ✅ Phase 2
- [ ] 13 Nerd Font installer scripts
- [ ] management/common/install/fonts/sgr-iosevka.sh
- [ ] management/common/install/fonts/firacodescript.sh

### Medium Priority (Phases 4-6)

- [ ] 11 GitHub release tool scripts
- [ ] management/common/install/plugins/shell-plugins.sh
- [ ] management/common/install/plugins/tmux-plugins.sh
- [ ] management/common/install/plugins/nvim-plugins.sh
- [ ] management/common/install/plugins/tpm.sh
- [ ] Create: management/common/install/plugins/tinty-themes.sh
- [ ] Create: management/common/install/custom-apps/sess.sh
- [ ] Create: management/common/install/custom-apps/toolbox.sh

### Lower Priority (Phases 7-8)

- [ ] management/common/install/github-releases/tenv.sh
- [ ] management/common/lib/failure-logging.sh
- [ ] All scripts with redundant success logging (audit needed)

**Total Files**: ~60-70 files (exact count from grep results)

---

## Notes

- This is a large refactor touching many files
- Suggest implementing phase-by-phase, testing each phase before moving to next
- Some issues (neovim terminal size) may require research and testing
- Priority should be on removing confusion and adding missing information
- Secondary priority on aesthetics and spacing
