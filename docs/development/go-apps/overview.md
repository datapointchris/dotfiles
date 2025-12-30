# Go Applications

This dotfiles repository includes custom Go applications for workflow automation and tool discovery. All Go apps are built from source and installed to `~/go/bin/`, which is added to PATH by the shell configuration.

## Applications

### sess - Session Manager

Fast tmux session manager that replaces sesh. Provides interactive session selection, creation, and switching with integration for tmuxinator projects and configurable default sessions.

**Location**: `apps/common/sess/`

**Installation**:

```bash
cd ~/dotfiles/apps/common/sess
task install
# Installs to ~/go/bin/sess
```

**Key features**:

- Interactive session picker with gum
- Create or switch to sessions by name
- List all sessions (tmux + tmuxinator + defaults)
- Platform-specific default sessions (configured in `~/.config/sess/sessions-{platform}.yml`)
- Fast startup and low memory footprint

See [Session Manager Reference](../../apps/sess.md) for usage details.

### toolbox - Tool Discovery

Tool discovery and documentation system that helps explore the 30+ CLI tools installed in your dotfiles. Provides searchable registry with descriptions, examples, and installation information.

**Location**: `apps/common/toolbox/`

**Installation**:

```bash
cd ~/dotfiles/apps/common/toolbox
task install
# Installs to ~/go/bin/toolbox
```

**Key features**:

- List all tools by category
- Search by name, description, or tags
- Show detailed tool information with examples
- Interactive category browser
- Registry-based architecture (YAML configuration)

See [Toolbox Reference](../../apps/toolbox.md) for usage details.

## Development Workflow

### Building Applications

Each Go application has its own Taskfile for build automation:

```bash
cd ~/dotfiles/apps/common/{app}
task build        # Build binary
task install      # Build and install to ~/go/bin
task test         # Run tests
task clean        # Clean build artifacts
```

### Testing

Go apps use Go's standard testing framework with table-driven tests and the Bubbletea test utilities for TUI testing:

```bash
cd ~/dotfiles/apps/common/{app}
task test         # Run all tests
go test -v ./...  # Verbose test output
go test -run TestSpecificFunction  # Run specific test
```

### Project Structure

Standard Go project layout:

```text
apps/common/{app}/
├── cmd/              # Command implementations
├── internal/         # Internal packages (not importable)
│   ├── config/       # Configuration loading
│   ├── display/      # UI components (Bubbletea)
│   └── models/       # Data structures
├── go.mod            # Go module definition
├── go.sum            # Dependency checksums
├── Taskfile.yml      # Build automation
└── README.md         # App-specific documentation
```

## Development Standards

Follow the coding standards and patterns documented in:

- [Go Development Standards](go-development.md) - Coding conventions, error handling, testing
- [Go Quick Reference](go-quick-reference.md) - Common Go patterns and idioms
- [Bubbletea Quick Reference](bubbletea-quick-reference.md) - TUI development with Bubbletea

## Adding New Applications

Create new Go applications following the established patterns:

1. **Create directory structure**:

   ```bash
   mkdir -p apps/common/{app}/{cmd,internal}
   ```

2. **Initialize Go module**:

   ```bash
   cd apps/common/{app}
   go mod init github.com/datapointchris/dotfiles/apps/common/{app}
   ```

3. **Create Taskfile.yml**:
   Copy from existing app (sess or toolbox) and modify for your app.

4. **Add to installation**:
   Add your app to the Go app installation in `install.sh` or create an install script in `management/common/install/`.

5. **Follow standards**:
   Use the patterns from existing apps (sess, toolbox) for configuration loading, display components, and testing.

## Migration History

Both `sess` and `toolbox` were migrated from bash scripts to Go applications in November 2025 for improved performance, reliability, and maintainability. The migration provided:

- **Type safety** - Compile-time error detection
- **Testing** - Unit tests with table-driven tests and TUI test utilities
- **Performance** - Faster startup and execution
- **Maintainability** - Clear structure and separation of concerns
- **Cross-platform** - Single binary works on all platforms

See `docs/archive/go-migration/` for detailed migration documentation (planning, strategy, and completion report).

## Troubleshooting

**Command not found after installation**:

Verify `~/go/bin` is in your PATH:

```bash
echo $PATH | grep "$HOME/go/bin"
```

If not, restart your shell or run `exec zsh`.

**Build failures**:

Ensure Go is installed and up to date:

```bash
go version  # Should be 1.23+
```

If Go is missing, run the installation task:

```bash
cd ~/dotfiles
task install  # Installs Go as part of GitHub release tools phase
```

**Import errors**:

Clean and rebuild:

```bash
cd ~/dotfiles/apps/common/{app}
task clean
go mod tidy
task install
```
