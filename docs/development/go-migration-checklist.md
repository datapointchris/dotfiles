# Go Migration Checklist

Detailed task checklist for the Go migration project. Track your progress here.

## Pre-Migration Setup

- [ ] Review full [migration strategy](./go-migration-strategy.md)
- [ ] Review [Go development standards](./go-development.md)
- [ ] Install Go 1.21+ (`brew install go`)
- [ ] Verify go installation (`go version`)
- [ ] Read [Quick Start Guide](./go-migration-quick-start.md)
- [ ] Backup current bash scripts to `-legacy` versions
- [ ] Create git branch for migration work

## Phase 1: Session Manager (Target: 1-2 weeks)

### Week 1: Foundation

**Project Setup (Day 1-2)**

- [ ] Create `tools/session-go` directory structure
- [ ] Initialize go module (`go mod init session-go`)
- [ ] Add dependencies (cobra, bubbletea, lipgloss, yaml.v3)
- [ ] Create `main.go` entry point
- [ ] Create `cmd/root.go` with basic CLI
- [ ] Create `README.md` for session-go
- [ ] Create `.gitignore` (add vendor/, binary)
- [ ] Add to `taskfiles/go.yml`
- [ ] Test basic build (`go build`)
- [ ] Verify `session-go --help` works

**Session Config Parser (Day 3-4)**

- [ ] Create `internal/config/config.go`
- [ ] Define `SessionConfig` struct with YAML tags
- [ ] Define `Session` struct
- [ ] Implement `LoadConfig(path string)` function
- [ ] Implement config validation
- [ ] Add default config support
- [ ] Handle missing config gracefully
- [ ] Create `internal/config/config_test.go`
- [ ] Add test cases for valid configs
- [ ] Add test cases for invalid configs
- [ ] Add golden file tests with testdata
- [ ] Achieve >80% test coverage
- [ ] Test with actual `sessions-macos.yml`

**Tmux Integration (Day 5-6)**

- [ ] Create `internal/tmux/client.go`
- [ ] Implement `ListSessions()` function
- [ ] Implement `SessionExists(name)` function
- [ ] Implement `CreateSession(name, dir)` function
- [ ] Implement `SwitchClient(name)` function
- [ ] Implement `KillSession(name)` function
- [ ] Implement `IsInTmux()` detection
- [ ] Handle tmux not running gracefully
- [ ] Create `internal/tmux/client_test.go`
- [ ] Mock tmux commands for testing
- [ ] Test all tmux operations
- [ ] Test error cases

**Tmuxinator Integration (Day 7)**

- [ ] Create `internal/tmux/tmuxinator.go`
- [ ] Implement `ListProjects()` function
- [ ] Implement `StartProject(name, attach)` function
- [ ] Handle tmuxinator not installed
- [ ] Create `internal/tmux/tmuxinator_test.go`
- [ ] Test project listing
- [ ] Test project starting

### Week 2: UI and Polish

**Interactive UI (Day 8-10)**

- [ ] Create `internal/ui/model.go`
- [ ] Define bubbletea model struct
- [ ] Implement `Init()` method
- [ ] Implement `Update()` method
- [ ] Implement `View()` method
- [ ] Add keyboard navigation (arrows, j/k)
- [ ] Add session icons (● ⚙ ○)
- [ ] Add "Create New Session" option
- [ ] Handle session selection
- [ ] Handle creating new sessions
- [ ] Add styling with lipgloss
- [ ] Create `internal/ui/model_test.go`
- [ ] Test navigation logic
- [ ] Test state updates

**CLI Commands (Day 11-12)**

- [ ] Implement `cmd/interactive.go` (default)
- [ ] Implement `cmd/list.go`
- [ ] Implement `cmd/create.go`
- [ ] Implement `cmd/kill.go`
- [ ] Implement `cmd/defaults.go`
- [ ] Add `--version` flag
- [ ] Add `--help` documentation
- [ ] Test all commands manually

**Testing & Polish (Day 13-14)**

- [ ] Run all tests (`go test ./...`)
- [ ] Verify test coverage >80%
- [ ] Fix any failing tests
- [ ] Test with real tmux sessions
- [ ] Test with tmuxinator projects
- [ ] Test default session creation
- [ ] Add error handling improvements
- [ ] Add helpful error messages
- [ ] Benchmark startup time (<50ms target)
- [ ] Profile if needed
- [ ] Code cleanup and formatting
- [ ] Run `go fmt ./...`
- [ ] Run `go vet ./...`

**Deployment (Day 14)**

- [ ] Build production binary (`task go:build-session`)
- [ ] Install to `~/.local/bin`
- [ ] Create bash wrapper script
- [ ] Update symlinks if needed
- [ ] Test wrapper script
- [ ] Backup original bash `sess` to `sess-legacy`
- [ ] Switch default `sess` to wrapper
- [ ] Test daily workflows
- [ ] Document any issues
- [ ] Fix critical bugs

**Stabilization (Week 3)**

- [ ] Use `session-go` exclusively for 1 week
- [ ] Track any bugs or regressions
- [ ] Fix issues as they arise
- [ ] Get feedback (if applicable)
- [ ] Verify zero regressions
- [ ] Update documentation
- [ ] Consider Phase 1 complete

## Phase 2: Menu Core (Target: 3-4 weeks)

### Week 1: Foundation

**Project Setup (Day 1)**

- [ ] Create `tools/menu-go` directory structure
- [ ] Initialize go module (`go mod init menu-go`)
- [ ] Add dependencies (reuse from session-go)
- [ ] Create `main.go` entry point
- [ ] Create `cmd/root.go`
- [ ] Create `README.md`
- [ ] Add to `taskfiles/go.yml`
- [ ] Test basic build

**Registry Parsers (Day 2-5)**

Commands Registry:
- [ ] Create `internal/registry/commands.go`
- [ ] Define `CommandRegistry` struct
- [ ] Define `Command` struct
- [ ] Implement `LoadCommands(path)` function
- [ ] Implement validation
- [ ] Create `internal/registry/commands_test.go`
- [ ] Test with actual commands.yml

Workflows Registry:
- [ ] Create `internal/registry/workflows.go`
- [ ] Define `WorkflowRegistry` struct
- [ ] Define `Workflow` struct
- [ ] Implement `LoadWorkflows(path)` function
- [ ] Create tests
- [ ] Test with actual workflows.yml

Learning Registry:
- [ ] Create `internal/registry/learning.go`
- [ ] Define `LearningRegistry` struct
- [ ] Define `LearningTopic` struct
- [ ] Implement `LoadLearning(path)` function
- [ ] Create tests
- [ ] Test with actual learning.yml

Config and Categories:
- [ ] Create `internal/config/menu_config.go`
- [ ] Parse `config.yml`
- [ ] Parse `categories.yml`
- [ ] Test config loading
- [ ] Achieve >85% coverage on all parsers

### Week 2: Navigation

**Menu Navigation (Day 6-9)**

- [ ] Create `internal/menu/navigation.go`
- [ ] Implement category selection UI
- [ ] Implement item list for each category
- [ ] Implement detail view with paging
- [ ] Implement breadcrumb navigation
- [ ] Add keyboard shortcuts (s, t, n, c, g, etc.)
- [ ] Add back navigation
- [ ] Create `internal/menu/navigation_test.go`
- [ ] Test navigation state machine
- [ ] Test all keyboard shortcuts

**Context Detection (Day 10-11)**

- [ ] Create `internal/context/detector.go`
- [ ] Implement `IsInGitRepo()` function
- [ ] Implement `HasTaskfile()` function
- [ ] Implement `IsInTmux()` function
- [ ] Implement `DetectPlatform()` function
- [ ] Implement `GetProjectName()` function
- [ ] Create tests
- [ ] Test context detection logic

### Week 3: Integrations

**Task Integration (Day 12-13)**

- [ ] Create `internal/task/client.go`
- [ ] Implement `ListTasks()` function
- [ ] Implement `GetTaskSummary(name)` function
- [ ] Implement `RunTask(name)` function
- [ ] Create tests
- [ ] Test with real Taskfile

**Session Integration (Day 14)**

- [ ] Import session-go as library (or shell out)
- [ ] Implement session launching from menu
- [ ] Test integration

**Notes Integration (Day 15)**

- [ ] Create placeholder for notes
- [ ] Document future integration plan

### Week 4: Testing and Deployment

**Comprehensive Testing (Day 16-18)**

- [ ] Run all tests (`go test ./...`)
- [ ] Verify test coverage >85%
- [ ] Integration tests for end-to-end flows
- [ ] Test all menu categories
- [ ] Test all navigation paths
- [ ] Test context detection
- [ ] Test integrations
- [ ] Performance benchmarks
- [ ] Startup time <100ms verification

**Polish (Day 19-20)**

- [ ] Error handling review
- [ ] Add logging support
- [ ] Improve error messages
- [ ] Code cleanup
- [ ] Documentation review
- [ ] README updates

**Deployment (Day 21)**

- [ ] Build production binary
- [ ] Install to `~/.local/bin`
- [ ] Create bash wrapper
- [ ] Backup original `menu` to `menu-legacy`
- [ ] Switch default to wrapper
- [ ] Test all workflows
- [ ] Fix critical bugs

**Stabilization (Week 5)**

- [ ] Use `menu-go` exclusively for 1 week
- [ ] Track issues
- [ ] Fix bugs
- [ ] Verify zero regressions
- [ ] Update documentation
- [ ] Consider Phase 2 complete

## Phase 3: Enhanced Features (Ongoing)

**Search Feature (1 week)**

- [ ] Design search API
- [ ] Implement search across registries
- [ ] Add `menu search <query>` command
- [ ] Add fuzzy matching
- [ ] Create tests
- [ ] Document usage

**Recent Items (2-3 days)**

- [ ] Design tracking mechanism
- [ ] Implement access tracking
- [ ] Add `menu recent` command
- [ ] Create tests
- [ ] Document usage

**Notes Integration (1-2 weeks)**

- [ ] Design notes workflow
- [ ] Integrate with nb/Obsidian
- [ ] Add note creation commands
- [ ] Create tests
- [ ] Document usage

**Suggestions (TBD)**

- [ ] Design suggestion engine
- [ ] Implement context-based suggestions
- [ ] Add `menu suggest` command
- [ ] Create tests

**Web UI (Optional, 2-3 weeks)**

- [ ] Design web interface
- [ ] Implement HTTP server
- [ ] Create frontend
- [ ] Add `menu serve` command
- [ ] Document usage

## Post-Migration

**Cleanup**

- [ ] Delete `menu-legacy` bash script
- [ ] Delete `sess-legacy` bash script
- [ ] Remove bash-specific code
- [ ] Update all documentation
- [ ] Update CLAUDE.md
- [ ] Remove old references

**Documentation**

- [ ] Write migration summary
- [ ] Document lessons learned
- [ ] Update architecture docs
- [ ] Create learning document if needed
- [ ] Add to changelog

**Celebration**

- [ ] Reflect on improvements
- [ ] Enjoy faster, more reliable tools
- [ ] Plan next features
- [ ] Share experience (blog post?)

## Notes Section

Use this space to track issues, ideas, and observations during migration:

### Issues Encountered

*Add issues here as you encounter them*

### Performance Notes

*Track startup times, bottlenecks, optimizations*

### Feature Ideas

*Ideas for future enhancements*

### Lessons Learned

*Things to remember for next time*
