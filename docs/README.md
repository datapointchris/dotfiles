# Documentation

Comprehensive documentation for cross-platform dotfiles repository.

## Structure

**Getting Started**: [Quickstart](getting-started/quickstart.md) | [Installation](getting-started/installation.md) | [First Config](getting-started/first-config.md)

**Architecture**: [Overview](architecture/index.md)

**Reference**: [Platforms](reference/platforms.md) | [Tools](reference/tools.md) | [Troubleshooting](reference/troubleshooting.md) | [Corporate](reference/corporate.md)

**Development**: [Testing](development/testing.md) | [Publishing](publishing.md)

**Changelog**: [Summary](changelog.md) | [Detailed Entries](changelog/)

## Quick Navigation

| Need to... | Go to... |
|------------|----------|
| Install dotfiles | [Quickstart](getting-started/quickstart.md) |
| Understand architecture | [Architecture Overview](architecture/index.md) |
| Fix an issue | [Troubleshooting](reference/troubleshooting.md) |
| Check tool usage | Run `tools show <name>` |
| Test on VMs | [VM Testing Guide](development/testing.md) |
| Work in corporate network | [Corporate Setup](reference/corporate.md) |

## Key Principles

- **DRY**: Shared configs in `common/`, platform overrides only
- **Direct**: Task for coordination, tools for commands
- **Cross-platform**: Version managers (uv, nvm) for consistency
- **Testable**: VM-based testing for all platforms

## Documentation

Built with MkDocs Material. See [Publishing Guide](publishing.md) for deployment.
