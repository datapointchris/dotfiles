# Workflow Documentation

This directory contains documentation about efficient workflows and usage patterns for the dotfiles environment.

## Contents

### [AeroSpace + Tmux + Neovim Workflow](./aerospace-tmux-neovim-workflow.md)

Comprehensive guide covering:

- How the three-layer hierarchy works (AeroSpace → Tmux → Neovim)
- When to use workspaces vs sessions vs windows vs panes vs tabs vs splits vs buffers
- Decision trees for "where should I split next?"
- Complete keybinding reference across all three tools
- Single large monitor workflow optimization
- Example workflows for different development scenarios
- What NOT to do (redundancy analysis)
- Power user tips

**Quick Reference:**

- Use **buffers** in Neovim as your primary file navigation (not tabs!)
- Use **Tmux windows** for related tasks, not multiple terminals
- Use **AeroSpace workspaces** for major project/context separation
- Keep it simple: 2-4 windows per session, 2-3 panes per window

## Future Topics

Potential future workflow documentation to add:

- Git workflow integration with the three-layer setup
- Shell scripting workflow and testing patterns
- Documentation workflow (mdbook, markdown, etc.)
- Multi-monitor workflow adaptations
- Remote development workflow (SSH + Tmux)
