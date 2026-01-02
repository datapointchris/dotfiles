# Go Applications

Custom Go applications for workflow automation and tool discovery. Apps are installed from GitHub via `go install` and binaries live in `~/go/bin/`.

## Applications

### sess - Session Manager

Fast tmux session manager with interactive selection, creation, and switching. Integrates with tmuxinator projects and configurable default sessions.

**Installation**: `go install github.com/datapointchris/sess/cmd/sess@latest`

**Key features**:

- Interactive session picker with gum
- Create or switch to sessions by name
- List all sessions (tmux + tmuxinator + defaults)
- Platform-specific default sessions (`~/.config/sess/sessions-{platform}.yml`)

See [Session Manager Reference](../../apps/sess.md) for usage details.

### toolbox - Tool Discovery

Tool discovery and documentation system for exploring CLI tools. Provides searchable registry with descriptions, examples, and installation information.

**Installation**: `go install github.com/datapointchris/toolbox@latest`

**Key features**:

- List all tools by category
- Search by name, description, or tags
- Show detailed tool information with examples
- Interactive category browser

See [Toolbox Reference](../../apps/toolbox.md) for usage details.

## Development Workflow

Development happens in `~/tools/` with source code pushed to GitHub.

### Testing Changes Locally

```bash
cd ~/tools/sess
go run ./cmd/sess     # Test changes
go build -o sess ./cmd/sess  # Build local binary
task test             # Run tests
```

### Publishing Changes

```bash
cd ~/tools/sess
git add -A && git commit -m "feat: add feature"
git push

# Update installed version
go install github.com/datapointchris/sess/cmd/sess@latest
```

### Project Structure

```text
~/tools/sess/
├── cmd/sess/         # Main entry point
├── internal/         # Internal packages
│   ├── config/       # Configuration loading
│   ├── display/      # UI components (Bubbletea)
│   └── models/       # Data structures
├── go.mod            # Go module definition
├── go.sum            # Dependency checksums
├── Taskfile.yml      # Build automation
└── README.md         # Documentation
```

## Development Standards

Follow the coding standards and patterns documented in:

- [Go Development Standards](go-development.md) - Coding conventions, error handling, testing
- [Go Quick Reference](go-quick-reference.md) - Common Go patterns and idioms
- [Bubbletea Quick Reference](bubbletea-quick-reference.md) - TUI development with Bubbletea

## Adding New Go Applications

1. **Create repository in ~/tools/**:

   ```bash
   mkdir -p ~/tools/{app}
   cd ~/tools/{app}
   go mod init github.com/datapointchris/{app}
   git init
   ```

2. **Add to packages.yml** for automatic installation:

   ```yaml
   go_tools:
     - name: {app}
       package: github.com/datapointchris/{app}
   ```

3. **Push to GitHub** and install:

   ```bash
   git remote add origin git@github.com:datapointchris/{app}.git
   git push -u origin main
   go install github.com/datapointchris/{app}@latest
   ```

## Troubleshooting

**Command not found after installation**:

Verify `~/go/bin` is in your PATH:

```bash
echo $PATH | grep "$HOME/go/bin"
```

If not, restart your shell or run `exec zsh`.

**Update to latest version**:

```bash
go install github.com/datapointchris/{app}@latest
```

**Import errors during development**:

```bash
cd ~/tools/{app}
go mod tidy
```
