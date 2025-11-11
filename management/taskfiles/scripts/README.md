# Taskfile Helper Scripts

Shell scripts used by taskfiles for complex operations.

## Why Separate Scripts?

Following Taskfile best practices:

- Complex shell logic moved to separate scripts
- Easier to test and debug
- Better error handling with `set -euo pipefail`
- Cleaner taskfile YAML

## Usage

Scripts are called from taskfiles:

```yaml
tasks:
  install-node:
    cmds:
      - NVM_DIR={{.NVM_DIR}} {{.ROOT_DIR}}/management/taskfiles/scripts/nvm-install-node.sh {{.NODE_VERSION}}
```

## Scripts

- **nvm-install-node.sh** - Install specific Node.js version via nvm
- **nvm-install-lts.sh** - Install latest LTS Node.js via nvm
- **npm-install-globals.sh** - Install npm global packages (requires nvm)

All scripts:

- Exit on error (`set -euo pipefail`)
- Are executable (`chmod +x`)
- Handle their own error messages
- Return non-zero on failure
