# Add READMEs and Structured Error Reporting to Language Managers

**Status**: Planning
**Date**: 2025-12-07

## Decisions Made

1. ✅ Skip Pattern C abstraction (not worth it for 3 scripts)
2. ✅ Add structured error reporting to all language managers
3. ✅ Create README files in installer directories (for Claude Code navigation)
4. ✅ No bootstrap scripts (explicit sourcing is better)

## Work Items

### 1. Create README Files

Create README.md in each installer directory explaining the pattern:

#### Files to Create

- [ ] `management/common/install/github-releases/README.md`
- [ ] `management/common/install/language-managers/README.md`
- [ ] `management/common/install/language-tools/README.md`
- [ ] `management/common/install/custom-installers/README.md`
- [ ] `management/common/install/fonts/README.md`
- [ ] `management/common/install/plugins/README.md`

#### README Template Structure

```markdown
# {Category} Installers

## Pattern

[Explain the installation pattern]

## When to Use

[When to add a new installer to this directory]

## Example

[Show a complete example]

## Adding a New Tool

[Step-by-step instructions]
```

### 2. Add Structured Error Reporting to Language Managers

Update all 5 language manager scripts to use `output_failure_data()`:

#### Files to Update

- [ ] `management/common/install/language-managers/uv.sh`
- [ ] `management/common/install/language-managers/nvm.sh`
- [ ] `management/common/install/language-managers/go.sh`
- [ ] `management/common/install/language-managers/rust.sh`
- [ ] `management/common/install/language-managers/tenv.sh`

#### Changes Needed

1. Source `install-helpers.sh` for `output_failure_data()` function
2. Add error handling around critical operations
3. Call `output_failure_data()` before `exit 1` on failures
4. Provide manual installation steps in failure data

#### Pattern to Follow

```bash
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"  # ADD THIS

print_banner "Installing ..."

if already_installed; then
  log_success "already installed"
else
  log_info "Installing..."

  if ! installation_command; then
    # ADD STRUCTURED ERROR REPORTING
    manual_steps="Manual installation steps here..."
    output_failure_data "tool-name" "download-url" "version" "$manual_steps" "Reason for failure"
    log_error "Installation failed"
    exit 1
  fi

  log_success "installed"
fi
```

### 3. Add Integration Test for Language Manager Pattern

Create test to validate language managers output structured failure data:

#### File to Create

- [ ] `tests/install/integration/language-managers-pattern.sh`

#### Test Should Validate

1. Mock language manager installer outputs `FAILURE_TOOL`
2. Mock language manager installer outputs `FAILURE_URL`
3. Mock language manager installer outputs `FAILURE_VERSION`
4. Mock language manager installer outputs `FAILURE_REASON`
5. Mock language manager installer outputs `FAILURE_MANUAL_START/END`
6. `run_installer()` wrapper correctly captures and logs the data

#### Test Pattern

Based on existing `github-releases-pattern.sh` test, adapted for language managers.

### 4. Manual Testing

After implementation, manually test each language manager to ensure:

- [ ] Successful installation still works
- [ ] Failure conditions trigger structured error output
- [ ] Error messages are helpful and accurate
- [ ] Manual installation steps are correct

## Implementation Order

1. **First**: Create all README files (establishes patterns)
2. **Second**: Create integration test (TDD approach)
3. **Third**: Update language manager scripts (one at a time)
4. **Fourth**: Run tests after each script update
5. **Fifth**: Manual testing of each updated script

## Notes

- Keep existing functionality intact - only add error reporting
- Don't change the installation logic, just wrap with error handling
- Each language manager may have unique failure points to handle
- Manual steps should be specific to each tool's installation method

## Success Criteria

- [ ] All README files created and informative
- [ ] All language manager scripts source `install-helpers.sh`
- [ ] All language manager scripts call `output_failure_data()` on failures
- [ ] Integration test passes
- [ ] Manual testing confirms installations still work
- [ ] Error reporting is consistent across all installers
