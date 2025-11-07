# Go Migration Strategy: Bash Menu System to Go

This document outlines a comprehensive strategy for migrating the bash-based menu system (`menu` and `sess` scripts) to Go, while maintaining functionality and enabling future enhancements.

## Quick Links

- [Quick Start Guide](./go-migration-quick-start.md) - Get started immediately
- [Go Development Standards](./go-development.md) - Coding standards and patterns
- [Menu System Architecture](../architecture/menu-system.md) - Current architecture

## Migration Overview

```
Phase 1: Session Manager (1-2 weeks)
├── sess (329 lines bash) → session-go
├── YAML config parser
├── Tmux/tmuxinator integration
└── Interactive TUI

Phase 2: Menu Core (3-4 weeks)
├── menu (420 lines bash) → menu-go
├── Registry parsers (commands, workflows, learning)
├── Category navigation
└── Context detection

Phase 3: Enhanced Features (Ongoing)
├── Search across registries
├── Fuzzy finding
├── Recent items
└── Notes integration
```

## Current State Analysis

### Bash Implementation

**Scripts:**
- `menu` (~420 lines) - Universal menu with category navigation
- `sess` (~329 lines) - Tmux session manager
- `fzf-functions.sh` (~216 lines) - Shell functions using fzf
- Total: ~965 lines of bash

**Data Layer:**
- YAML registries in `~/.config/menu/`:
  - `registry/commands.yml` - Shell commands, aliases, functions
  - `registry/workflows.yml` - Multi-step processes
  - `registry/learning.yml` - Learning resources with progress tracking
  - `sessions/sessions-<platform>.yml` - Default session configurations
  - `config.yml` - Main configuration
  - `categories.yml` - Category definitions

**External Dependencies:**
- `gum` - Interactive prompts and UI
- `fzf` - Fuzzy finding
- `tmux` - Terminal multiplexer
- `tmuxinator` - Tmux session templates
- `yq` - YAML processing (optional, falls back to grep/sed)
- `task` - Task runner integration
- `nb`, `buku` - Notes and bookmarks (future)

**Key Features:**
- Context-aware (detects git repos, Taskfiles)
- Platform-specific configs (macOS/WSL)
- Tmux popup integration (`prefix + m`)
- Progressive disclosure (menu → category → details)
- Session aggregation from 3 sources (active tmux, tmuxinator, defaults)

### Current Pain Points

1. **YAML Parsing**: Inconsistent parsing with grep/sed fallbacks when yq unavailable
2. **Error Handling**: Limited error messages, no logging
3. **Testing**: No automated tests for bash scripts
4. **Performance**: Multiple shell subprocesses for YAML parsing
5. **Maintainability**: String manipulation in bash is fragile
6. **Extensibility**: Adding features requires bash gymnastics
7. **Cross-platform**: Platform detection relies on environment variables

## Migration Goals

### Primary Objectives

1. **Improve reliability** - Better error handling, validation, logging
2. **Enhance testability** - Unit tests, integration tests, CI pipeline
3. **Increase maintainability** - Cleaner code structure, easier to extend
4. **Maintain UX** - Zero regression in user experience
5. **Enable future features** - Search, fuzzy finding, better integrations

### Non-Goals

1. Rewrite everything at once (incremental migration)
2. Change YAML registry format (keep data layer compatible)
3. Remove bash entirely (some things belong in shell)
4. Introduce complex dependencies (keep it simple)

## What to Migrate vs Keep

### Migrate to Go

**Core Logic:**
- YAML parsing and validation
- Configuration management
- Registry data structures and queries
- Session management logic
- Menu navigation state machine
- Tmux/tmuxinator integration
- Error handling and logging

**Why Go:**
- Strong typing for YAML schemas
- Better error handling
- Easy cross-compilation
- Fast startup time
- Great testing ecosystem
- Single binary deployment
- Standard library has everything needed

### Keep in Bash

**Shell-Specific Functions:**
- `fcd` - Uses shell's `cd` builtin (must stay in shell)
- `z` - Frecency tracking (requires shell integration)
- Other functions in `fzf-functions.sh` that modify shell state

**Integration Scripts:**
- Tmux key binding calling the menu (`prefix + m`)
- Shell aliases and functions that wrap the Go binary

**Why Bash:**
- Shell state modification (cd, environment variables)
- Direct shell integration
- Simpler for one-liners
- Already works well

### Platform-Specific Boundaries

```
┌─────────────────────────────────────────────┐
│            Go Binary (menu-go)              │
│  - YAML parsing                             │
│  - Business logic                           │
│  - Tmux integration                         │
│  - Interactive UI (bubbletea/gum)           │
│  - Platform detection                       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────┴───────────────────────────┐
│           Shell Integration                  │
│  - Shell functions (fcd, z)                 │
│  - Tmux key bindings                        │
│  - Shell aliases wrapping Go                │
└─────────────────────────────────────────────┘
```

## Migration Phases

### Phase 1: Session Manager (`sess` → `session-go`)

**Why Start Here:**
- Simpler scope (~329 lines)
- Clear inputs/outputs
- Limited external dependencies
- Immediate value (better session management)
- Learning opportunity before tackling `menu`

**Timeline:** 1-2 weeks

**Deliverables:**
1. Go binary: `session-go` (or `sess-go`)
2. YAML session config parser
3. Tmux/tmuxinator integration
4. Interactive mode with bubbletea
5. Unit tests (>80% coverage)
6. Bash wrapper for compatibility
7. Documentation

**Tasks:**

```yaml
1. Project Setup (1-2 days)
   - Create tools/session-go directory
   - Initialize go.mod
   - Setup dependencies (cobra, bubbletea, yaml.v3)
   - Create basic CLI structure
   - Add to taskfiles/go.yml for building

2. Session Config Parser (1-2 days)
   - Define Go structs for sessions YAML
   - Parse sessions-<platform>.yml
   - Validate session configs
   - Unit tests for parsing

3. Tmux Integration (1-2 days)
   - List active sessions
   - Create sessions
   - Switch sessions
   - Kill sessions
   - Detect if inside tmux

4. Tmuxinator Integration (1 day)
   - List tmuxinator projects
   - Start tmuxinator sessions
   - Handle errors gracefully

5. Interactive UI (2-3 days)
   - Bubbletea TUI
   - Session list with icons (● ⚙ ○)
   - Create new session flow
   - Keyboard navigation

6. Testing & Polish (2-3 days)
   - Unit tests for all logic
   - Integration tests with mock tmux
   - Error handling improvements
   - Performance testing

7. Deployment (1 day)
   - Build task in Taskfile
   - Install to ~/.local/bin
   - Bash wrapper script
   - Update symlinks
```

**Success Metrics:**
- Feature parity with bash `sess`
- <50ms startup time
- 0 regressions in functionality
- >80% test coverage
- Clean error messages

**Rollback Plan:**
- Keep bash `sess` as `sess-legacy`
- Symlink points to Go version
- Can switch back instantly if issues

### Phase 2: Menu Core (`menu` → `menu-go`)

**Why Second:**
- Builds on learnings from Phase 1
- More complex (multiple registries, categories)
- Needs robust YAML handling from Phase 1

**Timeline:** 3-4 weeks

**Deliverables:**
1. Go binary: `menu-go`
2. Registry parsers (commands, workflows, learning)
3. Category navigation system
4. Detail view with pager
5. Context detection (git, taskfile)
6. Comprehensive tests
7. Migration guide

**Tasks:**

```yaml
1. Project Setup (1 day)
   - Create tools/menu-go directory
   - Shared config with session-go
   - CLI framework (cobra)

2. Registry Parsers (3-4 days)
   - Commands registry struct & parser
   - Workflows registry struct & parser
   - Learning registry struct & parser
   - Config.yml parser
   - Categories.yml parser
   - Validation for all schemas
   - Unit tests

3. Menu Navigation (3-4 days)
   - Category selection UI
   - Item list for each category
   - Detail view with paging
   - Breadcrumb navigation (category → item → details → back)
   - Keyboard shortcuts (s, t, n, c, g, etc.)

4. Context Detection (1-2 days)
   - Git repo detection
   - Taskfile detection
   - Tmux detection
   - Platform detection
   - Conditional menu items

5. Integrations (2-3 days)
   - Task runner integration (show tasks)
   - Session integration (launch sess-go)
   - Notes integration (placeholder)

6. Testing (3-4 days)
   - Unit tests for all parsers
   - Integration tests for navigation
   - Golden file tests for YAML parsing
   - Mock filesystem tests
   - Performance benchmarks

7. Polish & Deploy (2-3 days)
   - Error handling
   - Logging
   - Build scripts
   - Documentation
   - Migration guide for users (you)
```

**Success Metrics:**
- Full feature parity with bash `menu`
- <100ms startup time
- 0 user-facing regressions
- >85% test coverage
- Better error messages than bash version

**Rollback Plan:**
- Keep bash `menu` as `menu-legacy`
- Symlink switching
- Can revert mid-migration

### Phase 3: Enhanced Features

**Why Last:**
- Foundation is solid
- Can add value incrementally
- Not blocking migration

**Timeline:** Ongoing (post-migration)

**Potential Features:**

1. **Search Across All Registries**
   ```bash
   menu search "quickfix"
   # Shows matches from commands, workflows, learning
   ```

2. **Fuzzy Finding**
   ```bash
   menu --fuzzy
   # Fuzzy search all entries
   ```

3. **Recent Items**
   ```bash
   menu recent
   # Show recently accessed items
   ```

4. **Suggestions**
   ```bash
   menu suggest
   # AI-powered suggestions based on context
   ```

5. **Notes Integration**
   ```bash
   menu notes workflow
   # Create workflow note
   ```

6. **Export/Import**
   ```bash
   menu export dotfiles-knowledge.json
   menu import from-old-system.json
   ```

7. **Web UI** (optional)
   ```bash
   menu serve
   # Launch web interface on localhost:8080
   ```

8. **Sync** (optional)
   ```bash
   menu sync
   # Sync learning progress, bookmarks to remote
   ```

## Directory Structure

```
dotfiles/
├── tools/
│   ├── session-go/              # Phase 1
│   │   ├── cmd/
│   │   │   └── root.go          # CLI commands
│   │   ├── internal/
│   │   │   ├── config/          # Config parsing
│   │   │   ├── session/         # Session logic
│   │   │   ├── tmux/            # Tmux integration
│   │   │   └── ui/              # TUI components
│   │   ├── main.go
│   │   ├── go.mod
│   │   ├── go.sum
│   │   └── README.md
│   │
│   ├── menu-go/                 # Phase 2
│   │   ├── cmd/
│   │   │   ├── root.go
│   │   │   ├── search.go        # Future: search command
│   │   │   └── recent.go        # Future: recent command
│   │   ├── internal/
│   │   │   ├── config/          # Shared config
│   │   │   ├── registry/        # Registry parsers
│   │   │   │   ├── commands.go
│   │   │   │   ├── workflows.go
│   │   │   │   ├── learning.go
│   │   │   │   └── common.go    # Shared types
│   │   │   ├── menu/            # Menu navigation
│   │   │   ├── context/         # Context detection
│   │   │   └── ui/              # TUI components
│   │   ├── main.go
│   │   ├── go.mod
│   │   ├── go.sum
│   │   └── README.md
│   │
│   └── symlinks/                # Existing Python tool
│
├── common/.local/bin/
│   ├── menu                     # Bash wrapper → menu-go
│   ├── menu-legacy              # Original bash (backup)
│   ├── sess                     # Bash wrapper → session-go
│   └── sess-legacy              # Original bash (backup)
│
├── taskfiles/
│   ├── go.yml                   # Go build tasks (new)
│   └── ...
│
└── docs/development/
    ├── go-migration-strategy.md # This file
    └── go-development.md        # Go coding standards (new)
```

### Why This Structure:

1. **Separate binaries** - `session-go` and `menu-go` are independent
2. **Internal packages** - Business logic is private, prevents misuse
3. **Shared patterns** - Config and UI can be shared via internal packages or separate module
4. **Standard layout** - Follows Go project layout conventions
5. **Clear migration** - Old bash scripts stay as `-legacy` during transition

## Build Process

### Build System

Use **Task** (already in use) with new `taskfiles/go.yml`:

```yaml
# taskfiles/go.yml
version: '3'

vars:
  SESSION_BIN: "{{.HOME}}/.local/bin/session-go"
  MENU_BIN: "{{.HOME}}/.local/bin/menu-go"

tasks:
  build-session:
    desc: Build session-go binary
    dir: tools/session-go
    cmds:
      - go build -o {{.SESSION_BIN}} .
    sources:
      - "**/*.go"
    generates:
      - "{{.SESSION_BIN}}"

  build-menu:
    desc: Build menu-go binary
    dir: tools/menu-go
    cmds:
      - go build -o {{.MENU_BIN}} .
    sources:
      - "**/*.go"
    generates:
      - "{{.MENU_BIN}}"

  build:
    desc: Build all Go tools
    deps:
      - build-session
      - build-menu

  test-session:
    desc: Test session-go
    dir: tools/session-go
    cmds:
      - go test ./... -v -cover

  test-menu:
    desc: Test menu-go
    dir: tools/menu-go
    cmds:
      - go test ./... -v -cover

  test:
    desc: Test all Go tools
    deps:
      - test-session
      - test-menu

  install-session:
    desc: Build and install session-go
    deps:
      - build-session
    cmds:
      - echo "Installed session-go to {{.SESSION_BIN}}"

  install-menu:
    desc: Build and install menu-go
    deps:
      - build-menu
    cmds:
      - echo "Installed menu-go to {{.MENU_BIN}}"

  install:
    desc: Build and install all Go tools
    deps:
      - install-session
      - install-menu

  clean:
    desc: Clean build artifacts
    cmds:
      - rm -f {{.SESSION_BIN}} {{.MENU_BIN}}
      - cd tools/session-go && go clean
      - cd tools/menu-go && go clean
```

### Installation Flow

```bash
# Development
task go:build-session      # Build session-go
task go:test-session       # Test it

# Production
task go:install-session    # Build and install to ~/.local/bin
task symlinks:link         # Create symlinks (if needed)
```

### Cross-Platform Builds (Future)

```yaml
# If ever needed for WSL/Arch
build-all-platforms:
  desc: Build for all platforms
  cmds:
    - GOOS=darwin GOARCH=arm64 go build -o bin/session-go-darwin-arm64
    - GOOS=darwin GOARCH=amd64 go build -o bin/session-go-darwin-amd64
    - GOOS=linux GOARCH=amd64 go build -o bin/session-go-linux-amd64
```

## Backward Compatibility Strategy

### During Migration

**Bash Wrapper Approach:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/sess
# Wrapper that calls Go binary

# Check if Go binary exists
if command -v session-go &>/dev/null; then
    exec session-go "$@"
else
    # Fallback to legacy bash version
    echo "session-go not found, using legacy bash version"
    exec sess-legacy "$@"
fi
```

**Benefits:**
- Transparent to users (you)
- Easy rollback (just remove session-go)
- Can A/B test both versions
- Symlinks still work

### Coexistence Period

**Week 1-2:**
- Both versions installed
- Go version is default
- Monitor for issues
- Keep detailed notes

**Week 3-4:**
- If stable, remove legacy versions
- If issues, fix and iterate
- Full cutover when confident

**Rollback Triggers:**
- Any data loss
- Broken core functionality
- Performance regression
- Annoying bugs

### YAML Compatibility

**No Changes to Registry Format:**
- Go must parse existing YAMLs
- No new required fields
- Optional fields can be added
- Strict validation (warn, don't error)

**Example:**

```go
// Strict parsing, but warnings for unknown fields
decoder := yaml.NewDecoder(file)
decoder.KnownFields(false) // Allow unknown fields

var config Config
if err := decoder.Decode(&config); err != nil {
    return fmt.Errorf("parse error: %w", err)
}

// Warn about deprecated fields, but continue
if config.DeprecatedField != "" {
    log.Warn("deprecated field 'deprecated_field' will be removed in future")
}
```

## Integration Points

### How Go Calls External Tools

**Tmux:**
```go
// internal/tmux/client.go
type Client struct{}

func (c *Client) ListSessions() ([]Session, error) {
    cmd := exec.Command("tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}")
    output, err := cmd.Output()
    // Parse and return
}

func (c *Client) SwitchClient(session string) error {
    return exec.Command("tmux", "switch-client", "-t", session).Run()
}
```

**Tmuxinator:**
```go
// internal/tmux/tmuxinator.go
type Tmuxinator struct{}

func (t *Tmuxinator) ListProjects() ([]string, error) {
    cmd := exec.Command("tmuxinator", "list")
    // Parse output
}

func (t *Tmuxinator) Start(project string, attach bool) error {
    args := []string{"start", project}
    if !attach {
        args = append(args, "--no-attach")
    }
    return exec.Command("tmuxinator", args...).Run()
}
```

**Task:**
```go
// internal/task/client.go
type Client struct {
    GitRoot string
}

func (c *Client) ListTasks() ([]Task, error) {
    cmd := exec.Command("task", "--list-all")
    cmd.Dir = c.GitRoot
    // Parse and return
}

func (c *Client) RunTask(name string) error {
    cmd := exec.Command("task", name)
    cmd.Dir = c.GitRoot
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    return cmd.Run()
}
```

### How Go Reads YAML Configs

**Centralized Config:**
```go
// internal/config/config.go
package config

type Config struct {
    Menu      MenuConfig      `yaml:"menu"`
    Tools     ToolsConfig     `yaml:"tools"`
    Notes     NotesConfig     `yaml:"notes"`
    Sessions  SessionsConfig  `yaml:"sessions"`
    Registry  RegistryConfig  `yaml:"registry"`
}

type MenuConfig struct {
    Height         int  `yaml:"height"`
    PreviewEnabled bool `yaml:"preview_enabled"`
    SearchEnabled  bool `yaml:"search_enabled"`
}

func Load() (*Config, error) {
    configPath := filepath.Join(os.Getenv("HOME"), ".config", "menu", "config.yml")
    // Load and parse
}
```

**Registry Parsing:**
```go
// internal/registry/commands.go
type CommandRegistry struct {
    Commands []Command `yaml:"commands"`
}

type Command struct {
    Name        string     `yaml:"name"`
    Type        string     `yaml:"type"`
    Category    string     `yaml:"category"`
    Description string     `yaml:"description"`
    Keywords    []string   `yaml:"keywords"`
    Command     string     `yaml:"command"`
    Examples    []Example  `yaml:"examples,omitempty"`
    Notes       string     `yaml:"notes,omitempty"`
    Related     []string   `yaml:"related,omitempty"`
    UseTLDR     bool       `yaml:"use_tldr,omitempty"`
    Platform    string     `yaml:"platform,omitempty"`
}

func LoadCommands() (*CommandRegistry, error) {
    path := filepath.Join(os.Getenv("HOME"), ".config", "menu", "registry", "commands.yml")
    // Load and validate
}
```

### How Go Integrates with Existing Shell Functions

**Not directly.** Shell functions stay in bash. Go provides the data and logic, bash provides shell integration.

**Example - Task Selection:**

Go binary shows task list, returns task name to stdout:
```bash
# Bash wrapper
selected_task=$(menu-go tasks --select)
if [ -n "$selected_task" ]; then
    task "$selected_task"
fi
```

Or Go handles it entirely:
```go
// menu-go can execute tasks directly
func runTask(name string) error {
    return exec.Command("task", name).Run()
}
```

## Risk Assessment & Mitigation

### High Risks

**1. Data Loss (YAML Corruption)**

**Risk:** Bad parsing could corrupt YAML files
- **Likelihood:** Low
- **Impact:** Critical
- **Mitigation:**
  - Read-only mode first (no writes)
  - Extensive YAML validation tests
  - Backup configs before migration
  - Version control everything

**2. Broken Workflows**

**Risk:** Missing features break daily workflows
- **Likelihood:** Medium
- **Impact:** High
- **Mitigation:**
  - Feature parity checklist
  - Manual testing of all workflows
  - Coexistence period
  - Easy rollback

### Medium Risks

**3. Performance Regression**

**Risk:** Go version is slower than bash
- **Likelihood:** Low
- **Impact:** Medium
- **Mitigation:**
  - Benchmark startup time
  - Profile if slow
  - Optimize hot paths
  - Target: <100ms startup

**4. Dependency Issues**

**Risk:** New dependencies cause installation problems
- **Likelihood:** Low
- **Impact:** Medium
- **Mitigation:**
  - Minimal dependencies
  - Vendoring if needed
  - Static binaries
  - Document all deps

### Low Risks

**5. Platform Compatibility**

**Risk:** Works on macOS, breaks on WSL
- **Likelihood:** Low
- **Impact:** Low (only use WSL occasionally)
- **Mitigation:**
  - Test on both platforms
  - Platform-specific code paths
  - CI for multiple platforms (future)

**6. Learning Curve**

**Risk:** Go is harder to maintain than bash
- **Likelihood:** Low
- **Impact:** Low
- **Mitigation:**
  - Good documentation
  - Standard patterns
  - Tests make changes safe
  - AI assistants help with Go

## Timeline & Estimates

### Phase 1: Session Manager (1-2 weeks)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| Week 1 | Setup, config parser, tmux integration | Working prototype |
| Week 2 | UI, testing, deployment | Production-ready `session-go` |

### Phase 2: Menu Core (3-4 weeks)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| Week 1 | Setup, registry parsers | YAML parsing complete |
| Week 2 | Navigation UI, context detection | Interactive menu working |
| Week 3 | Integrations, testing | Feature complete |
| Week 4 | Polish, documentation, deployment | Production-ready `menu-go` |

### Phase 3: Enhanced Features (Ongoing)

- Search: 1 week
- Fuzzy finding: 1 week
- Recent items: 2-3 days
- Notes integration: 1-2 weeks
- Web UI (optional): 2-3 weeks

**Total Migration Time:** 4-6 weeks

**Caveat:** This is solo development, fitting around other work. Add buffer time.

## Success Metrics

### Phase 1 (Session Manager)

- [ ] All `sess` commands work identically
- [ ] Startup time <50ms
- [ ] 0 functionality regressions
- [ ] Test coverage >80%
- [ ] Error messages are helpful
- [ ] Used daily for 2 weeks without issues

### Phase 2 (Menu Core)

- [ ] All `menu` categories work
- [ ] All navigation flows work
- [ ] Startup time <100ms
- [ ] Test coverage >85%
- [ ] YAML parsing is robust
- [ ] Used daily for 2 weeks without issues

### Phase 3 (Enhanced)

- [ ] At least 2 new features shipped
- [ ] Features actually get used
- [ ] No feature bloat
- [ ] Performance stays good

### Overall Migration

- [ ] Bash versions can be deleted
- [ ] No rollbacks needed
- [ ] Easier to add features
- [ ] Confidence in code quality
- [ ] Better error handling than before

## Open Questions & Decisions Needed

### 1. Binary Names

**Option A:** `session-go` and `menu-go`
- Pro: Clear distinction during migration
- Con: Longer names

**Option B:** `sess` and `menu` (replace directly)
- Pro: No wrapper needed
- Con: Harder rollback

**Recommendation:** Option A during migration, Option B after stabilization

### 2. UI Library

**Option A:** Use `gum` (shell out to existing tool)
- Pro: Consistent with bash version
- Pro: Familiar UI
- Con: External dependency
- Con: Extra process overhead

**Option B:** Use `bubbletea` (native Go TUI)
- Pro: Native Go, faster
- Pro: More control
- Pro: Better for complex UIs
- Con: Different look/feel
- Con: Learning curve

**Recommendation:** Option B (bubbletea) for better long-term control

### 3. Config Validation

**Option A:** Strict validation (error on unknown fields)
- Pro: Catches mistakes early
- Con: Breaks if you add experimental fields

**Option B:** Lenient validation (warn on unknown)
- Pro: More forgiving
- Con: Silent failures possible

**Recommendation:** Option B (lenient) for flexibility

### 4. Shared Code Between session-go and menu-go

**Option A:** Duplicate code
- Pro: Complete independence
- Con: DRY violation

**Option B:** Shared internal package
- Pro: Code reuse
- Con: Coupling between tools

**Option C:** Separate Go module for shared code
- Pro: Reusable, versioned
- Con: Over-engineering for small project

**Recommendation:** Option A initially, refactor to Option B if significant duplication emerges

## Next Steps

### Immediate Actions (This Week)

1. [ ] Review this strategy document
2. [ ] Make decisions on open questions
3. [ ] Create `tools/session-go` directory
4. [ ] Initialize Go module
5. [ ] Create `taskfiles/go.yml`
6. [ ] Document Go coding standards in `docs/development/go-development.md`

### Phase 1 Kickoff (Next Week)

1. [ ] Setup project structure
2. [ ] Add dependencies (cobra, bubbletea, yaml.v3)
3. [ ] Create basic CLI skeleton
4. [ ] Parse sessions YAML
5. [ ] Write first tests

### Tracking

Create a `todo.md` entry or project plan:

```markdown
# Go Migration Project

## Phase 1: Session Manager (2024-11-XX to 2024-11-XX)
- [ ] Project setup
- [ ] Session config parser
- [ ] Tmux integration
- [ ] Tmuxinator integration
- [ ] Interactive UI
- [ ] Testing & polish
- [ ] Deployment

## Phase 2: Menu Core (TBD)
...
```

## Appendix

### Example Go Code Patterns

**CLI Entry Point:**
```go
// tools/session-go/main.go
package main

import (
    "fmt"
    "os"
    "session-go/cmd"
)

func main() {
    if err := cmd.Execute(); err != nil {
        fmt.Fprintf(os.Stderr, "Error: %v\n", err)
        os.Exit(1)
    }
}
```

**Root Command:**
```go
// tools/session-go/cmd/root.go
package cmd

import (
    "github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
    Use:   "session-go",
    Short: "Fast tmux session manager",
    Long:  "A simple and fast tmux session manager built in Go",
}

func Execute() error {
    return rootCmd.Execute()
}
```

**Interactive Mode:**
```go
// tools/session-go/cmd/interactive.go
package cmd

import (
    tea "github.com/charmbracelet/bubbletea"
    "github.com/spf13/cobra"
    "session-go/internal/ui"
)

var interactiveCmd = &cobra.Command{
    Use:   "interactive",
    Short: "Interactive session selection",
    RunE: func(cmd *cobra.Command, args []string) error {
        p := tea.NewProgram(ui.NewModel())
        _, err := p.Run()
        return err
    },
}

func init() {
    rootCmd.AddCommand(interactiveCmd)
}
```

### Dependencies

**Core:**
- `gopkg.in/yaml.v3` - YAML parsing
- `github.com/spf13/cobra` - CLI framework
- `github.com/charmbracelet/bubbletea` - TUI framework
- `github.com/charmbracelet/lipgloss` - Terminal styling

**Testing:**
- Standard library `testing`
- `github.com/stretchr/testify` - Test assertions (optional)

**Total:** 4-5 dependencies, all well-maintained

### References

- [Go Project Layout](https://github.com/golang-standards/project-layout)
- [Cobra CLI Framework](https://github.com/spf13/cobra)
- [Bubbletea TUI Framework](https://github.com/charmbracelet/bubbletea)
- [YAML v3 Docs](https://pkg.go.dev/gopkg.in/yaml.v3)
- [Symlinks Python Tool](../../tools/symlinks/) - Reference implementation
