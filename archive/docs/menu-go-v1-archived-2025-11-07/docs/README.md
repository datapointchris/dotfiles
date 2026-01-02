# Menu-Go Documentation

Comprehensive documentation for the menu-go universal menu system.

## Table of Contents

### Features

- **[Favorites and Recents System](features/favorites-recents.md)**
  - Persistent state management
  - LRU cache implementation
  - Thread-safe operations with sync.RWMutex
  - Detailed Go language patterns and explanations

- **[Clipboard Support](features/clipboard-support.md)**
  - Cross-platform clipboard integration
  - Error handling patterns
  - Implementation details
  - Usage examples

- **[Syntax Highlighting](features/syntax-highlighting.md)**
  - Glamour integration for code highlighting
  - Markdown-based rendering
  - Fallback strategies
  - Functional options pattern

### Testing

- **[Testing Guide](testing/testing-guide.md)**
  - Test infrastructure overview
  - Table-driven test patterns
  - Mock integrations
  - Best practices and common challenges
  - Running tests and generating coverage

### Development

- **[Integration System](development/integration-system.md)**
  - Integration architecture
  - Four integration types (Static, Dynamic, Interactive, External)
  - Creating new integrations
  - Concurrent loading patterns
  - Best practices

## Documentation Philosophy

These docs are designed for:

1. **Learning Go** - Each doc explains Go patterns, idioms, and best practices
2. **Understanding the System** - Architecture decisions and trade-offs explained
3. **Contributing** - Step-by-step guides for adding features
4. **Reference** - Quick lookup for implementation details

## Quick Start

New to the project? Start here:

1. Read the [main README](../README.md) for project overview
2. Explore [Integration System](development/integration-system.md) for architecture
3. Check [Testing Guide](testing/testing-guide.md) before making changes
4. Review [Favorites and Recents](features/favorites-recents.md) for a deep dive into a complete feature

## Documentation Style

Each documentation file follows this structure:

- **Overview** - What the feature does
- **Implementation** - How it works with code examples
- **Go Language Features** - Patterns and idioms used
- **Use Cases** - Practical applications
- **Testing** - How to test the feature
- **Future Enhancements** - Potential improvements
- **Related Files** - Source code locations
- **See Also** - Links to related documentation

## Code Comments

In addition to these docs, the codebase has comprehensive inline comments:

- **`internal/integration/state.go`** - Fully documented with usage examples
- **Test files** - Comments explaining test patterns and why they're structured that way
- **Complex functions** - Detailed comments explaining algorithms and trade-offs

## Contributing to Documentation

When adding new features:

1. **Update existing docs** if the feature modifies existing behavior
2. **Create new docs** for substantial new features (> 100 LOC)
3. **Add inline comments** explaining Go patterns and design decisions
4. **Update this index** with links to new documentation

### Documentation Checklist

- [ ] Feature overview with use cases
- [ ] Implementation details with code examples
- [ ] Go language patterns explained
- [ ] Testing approach documented
- [ ] Related files referenced
- [ ] Links to related documentation
- [ ] Added to this index README

## Learning Resources

### Go Patterns Used in This Project

1. **Interfaces** - Integration interface for extensibility
2. **Functional Options** - Glamour renderer configuration
3. **Table-Driven Tests** - Comprehensive test coverage
4. **Goroutines & Channels** - Concurrent integration loading
5. **sync.RWMutex** - Thread-safe state management
6. **Context** - Cancellation and timeouts
7. **defer** - Resource cleanup
8. **Idempotent Operations** - Safe to call multiple times
9. **Defensive Copying** - Preventing race conditions
10. **Error Wrapping** - fmt.Errorf with %w

### External Libraries

- **Bubbletea** - Terminal UI framework
- **Bubbles** - TUI components
- **Lipgloss** - Terminal styling
- **Glamour** - Markdown rendering with syntax highlighting
- **Clipboard** - Cross-platform clipboard access

## Project Structure

```
menu-go/
├── cmd/menu/                    # Main entry point
├── internal/
│   ├── integration/             # Integration system
│   │   ├── state.go            # Persistent state (★ well documented)
│   │   ├── manager.go          # Integration manager
│   │   ├── types.go            # Core types
│   │   ├── testhelpers.go      # Test mocks
│   │   └── registries/         # Built-in integrations
│   ├── executor/               # Command execution
│   ├── registry/               # YAML loaders
│   ├── ui/                     # Bubbletea UI
│   └── testutil/               # Test infrastructure
├── docs/                       # This documentation
│   ├── features/               # Feature documentation
│   ├── testing/                # Testing guides
│   ├── development/            # Development guides
│   └── architecture/           # Architecture docs (TODO)
└── Taskfile.yml                # Task automation
```

## Testing

Run tests before submitting changes:

```bash
# Run all tests
go test ./...

# Run with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Run specific test
go test -run TestCommandsIntegration_Load ./internal/integration/registries
```

See [Testing Guide](testing/testing-guide.md) for detailed testing information.

## Building and Running

```bash
# Build
task build

# Run
task run

# Install to ~/.local/bin
task install

# Run tests
task test
```

## Getting Help

- **Issues** - Check GitHub issues for known problems
- **Code** - Read inline comments and documentation
- **Examples** - Look at existing integrations for patterns
- **Tests** - Test files show usage examples

## License

Part of the [dotfiles](https://github.com/ichrisbirch/dotfiles) repository.
