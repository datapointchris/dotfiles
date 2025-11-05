# Tool Discovery

The `tools` command helps discover and learn about the 30+ CLI tools installed in your dotfiles without heavy usage tracking or complex wrappers.

## Commands

### tools list

List all installed tools with categories.

```bash
tools          # same as tools list
tools list
```

Shows tools grouped by category with brief descriptions.

### tools show

Show detailed information about a specific tool.

```bash
tools show bat
tools show ripgrep
```

**Displays**:

- Description and why to use it
- Installation method (brew, npm, uv)
- Usage syntax
- Examples with explanations
- Related tools
- Documentation URL
- Installation status

### tools search

Search tools by description, tags, or name.

```bash
tools search git
tools search syntax
tools search linter
```

Returns matching tools with brief context.

### tools categories

List tool categories with counts.

```bash
tools categories
```

Shows categories like: file-viewer, search, version-control, linter, etc.

### tools count

Detailed breakdown by category with tool names.

```bash
tools count
```

Shows count per category plus which tools are in each category.

### tools random

Discover a random tool.

```bash
tools random
```

Picks a random tool and shows full details. Useful for learning about tools you might have forgotten.

### tools installed

Check installation status of all tools.

```bash
tools installed
```

Shows which tools are found in PATH vs not installed.

## Registry

Tools are defined in `docs/tools/registry.yml` with structured metadata.

**Tool entry format**:

```yaml
tool-name:
  category: file-viewer
  description: "Brief description"
  installed_via: brew              # brew, npm, uv, cargo, manual
  usage: "command [options] <args>"
  why_use: "Why this tool over alternatives"
  examples:
    - cmd: "command --option"
      desc: "What this does"
  see_also: [related-tool1, related-tool2]
  tags: [tag1, tag2]
  docs_url: "https://..."
```

**Categories**:

- file-viewer - bat, eza
- search - ripgrep, fzf
- navigation - zoxide
- version-control - git, gh, lazygit, git-delta
- editor - neovim
- terminal - tmux
- linter - ruff, eslint
- formatter - prettier, ruff-format
- language-server - typescript-language-server, basedpyright
- build - task, cmake
- container - docker
- system - htop, btop

## Adding Tools

Edit `docs/tools/registry.yml` and add new entry following the format above.

**Required fields**:

- category
- description
- installed_via
- usage

**Optional but recommended**:

- why_use (helps remember when to use it)
- examples (concrete usage patterns)
- see_also (discover related tools)
- tags (improve searchability)
- docs_url (quick reference)

After adding tools, run `tools list` to verify they appear.

## Philosophy

The tool discovery system prioritizes **discovery over tracking**.

**What it does**:

- Help remember what tools are available
- Show usage examples when needed
- Discover tools via random/search
- Quick reference without leaving terminal

**What it doesn't do**:

- Track usage statistics
- Wrap commands with shell functions
- Modify PATH or aliases
- Auto-install tools

**Why**: Keeps shell configs clean, no performance impact, easy to maintain, solves the real problem (tool awareness).

## Examples

```bash
# Forgot what bat does?
tools show bat

# What git tools are available?
tools search git

# Learn something new
tools random

# Quick category reference
tools categories

# Verify everything installed
tools installed
```

## Integration

The `tools` command integrates with other dotfiles systems:

**Installation**: Available after `symlinks relink <platform>` (symlinked from `common/.local/bin/tools`)

**Registry**: Lives in `docs/tools/registry.yml` for easy editing and version control

**Task automation**: `task install` ensures all tools in registry are installed

**Documentation**: Tools also documented in `docs/reference/tools.md` (overview) and this file (detailed reference)

## Troubleshooting

**Command not found**:

- Run `symlinks relink macos` (or wsl/arch)
- Verify `~/dotfiles/common/.local/bin` is in PATH
- Check script is executable: `chmod +x common/.local/bin/tools`

**Tool shows as not installed but it is**:

- Tool may not be in PATH
- Reload shell: `exec zsh`
- Check with `which <tool-name>`

**Registry not found**:

- Set `DOTFILES_REGISTRY` environment variable if dotfiles not in `~/dotfiles`
- Verify `docs/tools/registry.yml` exists
- Check YAML syntax with `yq . docs/tools/registry.yml`

**Search returns no results**:

- Search is case-insensitive substring match
- Try broader terms ("lint" instead of "linter")
- Use `tools list` to see all tools

## See Also

- [Tool Reference](tools.md) - Quick overview of available tools
- [Task Reference](tasks.md) - Installation automation
- [Symlinks](symlinks.md) - How tools command gets deployed
