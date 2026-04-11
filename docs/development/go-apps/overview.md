# Go Applications

Custom Go applications for workflow automation and tool discovery. Apps are installed from GitHub via `go install` and binaries live in `~/go/bin/`.

## Applications

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
cd ~/tools/toolbox
go run .              # Test changes
go build -o toolbox . # Build local binary
task test             # Run tests
```

### Publishing Changes

```bash
cd ~/tools/toolbox
git add -A && git commit -m "feat: add feature"
git push

# Update installed version
go install github.com/datapointchris/toolbox@latest
```

### Project Structure

Standard Go layout with `cmd/` entry point, `internal/` packages, `go.mod`/`go.sum`, and a `Taskfile.yml` for build automation.

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
