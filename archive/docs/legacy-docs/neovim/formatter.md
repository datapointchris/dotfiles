# Unified Formatter System: External Tools with LSP Fallback

## Problem Statement

Neovim 0.11 with native LSP creates a formatting consistency problem across different execution contexts:

1. **Manual formatting** (`<leader>fmt`) uses LSP formatting
2. **Auto-save formatting** uses LSP formatting  
3. **Pre-commit hooks** use external tools (stylua, ruff, prettier)

This creates three different formatting behaviors for the same code, leading to formatting wars and inconsistent results.

## Design Decision: External Formatter Priority

The solution prioritizes external formatters (matching pre-commit) with LSP as fallback, ensuring consistent behavior across all formatting contexts.

### Why External Formatters First?

**Performance**: External tools run as direct subprocesses versus LSP protocol overhead

- Stylua: ~50ms direct vs ~200ms via LSP
- Ruff: ~100ms direct vs ~300ms via LSP

**Reliability**: Specialized formatting tools versus general-purpose LSP implementations

- Prettier is the industry standard for JavaScript/TypeScript/JSON
- Stylua is the de facto Lua formatter
- Many LSPs actually delegate to these tools internally anyway

**Configuration**: External formatters read standard config files (`.prettierrc`, `.stylua.toml`) consistently, while LSP formatting configuration varies by server implementation.

### Alternative Approaches Rejected

**LSP-only formatting**:

- **Problem**: Inconsistent with pre-commit hooks
- **Performance**: Slower due to protocol overhead
- **Configuration**: LSP-specific formatting settings

**Plugin-based solutions** (conform.nvim):

- **Problem**: Additional dependency in a minimal-plugin philosophy
- **Corporate issues**: External dependencies in restricted environments
- **Complexity**: Abstraction layer over simple subprocess calls

## Architecture: Unified Formatter Module

All formatting logic centralizes in `utils/formatter.lua`, used by both manual keymaps and auto-save autocmds.

### Three-Tier Execution Strategy

1. **External formatter availability check**: Verify tool exists on PATH
2. **External formatter execution**: Try specialized tool first
3. **LSP fallback**: Use native LSP formatting if external fails

### Trade-offs Made

**Gained:**

- Consistent results across manual, auto-save, and pre-commit
- Best performance (external tools are faster)
- Industry-standard tool usage
- Corporate environment compatibility (system packages)

**Sacrificed:**

- Dependency on system-installed formatters
- More complex error handling (external + LSP paths)
- Some LSP-specific formatting features

## Integration Within Dotfiles Ecosystem

### Pre-commit Alignment

The formatter list directly matches pre-commit hook configuration:

- **Stylua**: `.stylua.toml` configuration shared between manual and pre-commit
- **Ruff**: System installation shared across all contexts
- **Prettier**: Standard `.prettierrc` files work everywhere

**Design choice**: System package alignment over plugin ecosystem

- **Why**: Corporate environments often block plugin managers
- **Why**: Explicit tool versions and locations
- **Trade-off**: Manual installation versus automated plugin management

### Cross-Platform Considerations

The system uses system packages rather than platform-specific plugin managers:

- **macOS**: Homebrew packages (`brew install stylua ruff prettier`)
- **WSL/Ubuntu**: Mix of apt, npm, cargo installs
- **Consistency**: Same tool versions across platforms via package managers

## Formatter Type Handling

The system accommodates two different external formatter interfaces:

### In-Place Formatters

Tools that modify files directly (stylua, rustfmt, gofmt):

- Execute with filename argument
- Reload file after formatting
- Simple subprocess model

### Stdin/Stdout Formatters  

Tools that process content through pipes (prettier, ruff format):

- Read buffer content into memory
- Pipe through formatter subprocess
- Replace buffer with formatted result
- More complex but handles large files better

**Design choice**: Handle both patterns versus forcing standardization

- **Why**: Industry tools use different interfaces naturally
- **Trade-off**: More complex implementation for broader compatibility

## Error Handling Philosophy

The system provides graceful degradation rather than hard failures:

1. **External tool missing**: Warn and fall back to LSP
2. **External tool fails**: Report error and fall back to LSP  
3. **LSP unavailable**: Continue silently (no formatting)

**Design choice**: Always allow continued editing versus strict formatting requirements

- **Why**: Formatting failures shouldn't block development workflow
- **Trade-off**: Potential for unformatted code versus development interruption

## Neovim LSP Ecosystem Context

### LSP vs External Formatter Reality

Many LSPs delegate to external formatters internally:

- `rust_analyzer` → `rustfmt`
- `gopls` → `gofmt`  
- `lua_ls` → (can delegate to stylua)

This system eliminates the middleman for better performance and control.

### Future Neovim Direction

Neovim 0.11+ native LSP doesn't eliminate external formatters—it provides better integration. The hybrid approach positions well for future evolution:

- External formatters remain the quality standard
- LSP integration improves for complex formatting scenarios
- System maintains best-of-both-worlds flexibility

## Maintenance Implications

### Adding New Languages

New formatter support requires only configuration table updates:

```lua
M.external_formatters = {
  -- Add new entry with tool name and arguments
  terraform = { cmd = 'terraform', args = { 'fmt', '-' } },
}
```

No plugin updates, dependency management, or complex configuration.

### Corporate Environment Adaptation

The system works in restricted environments because:

- **No external dependencies**: Uses system-installed tools only
- **No network requirements**: Tools installed via standard package managers
- **Transparent operation**: Easy to debug formatter issues

### Configuration Drift Prevention

External formatters read standard configuration files that don't change:

- `.stylua.toml` works identically across manual, auto-save, pre-commit
- `.prettierrc` maintains consistency across all JavaScript projects
- `ruff.toml` provides single source of Python formatting truth

This prevents the configuration drift common with LSP-specific formatting settings.

## Performance Characteristics

### Benchmark Context

External formatter performance matters because:

- **Auto-save formatting**: Runs on every file save
- **Large file handling**: Performance degrades with file size
- **Development flow**: Slow formatting interrupts coding

The 2-4x performance improvement from external tools versus LSP protocol significantly improves development experience, especially with frequent saves.

### Memory Efficiency

External formatters run as subprocesses and exit, versus persistent LSP servers consuming memory. For formatting-only operations, this provides better resource utilization.

## Evolution Path

The architecture accommodates future enhancements without breaking existing functionality:

- **Async external formatting**: Could parallelize formatter execution
- **Conditional formatting**: Could skip formatting for large files or specific contexts
- **Project-specific formatter selection**: Could override global formatter configuration

However, the core external-first philosophy provides immediate value without requiring these enhancements.
