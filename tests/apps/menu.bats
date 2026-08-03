#!/usr/bin/env bats
# ================================================================
# Unit tests for the menu CLI
# ================================================================
# The tmux lens reads its bindings out of the tmux-commands workflow card. That
# coupling broke silently once — the card moved from fenced columns to markdown
# tables and the parser kept matching the old shape, so the index simply lost
# every binding with nothing to show it had. These tests pin the card's format.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  export DOTFILES_DIR
  export MENU="$DOTFILES_DIR/apps/common/menu"
  # Redirecting XDG_DATA_HOME moves the toolbox registry too, which the tools
  # lens needs; point it back at the repo source so only the card is a fixture.
  export TOOLBOX_REGISTRY="$DOTFILES_DIR/configs/common/.local/share/toolbox/registry.yml"
}

setup() {
  TEST_DIR=$(mktemp -d)
  export XDG_DATA_HOME="$TEST_DIR/data"
  mkdir -p "$XDG_DATA_HOME/workflows"
  cat >"$XDG_DATA_HOME/workflows/tmux-commands.md" <<'EOF'
---
tags: [tmux]
---

# tmux keybindings

## Panes

| prefix + \|  | split vertical  |
| prefix + z   | zoom pane       |

## Copy mode

| v | begin selection |
EOF
}

teardown() {
  rm -rf "$TEST_DIR"
}

@test "index includes tmux bindings from the card" {
  run "$MENU" __index
  assert_success
  assert_output --partial "zoom pane"
}

@test "index parses a binding whose key is an escaped pipe" {
  run "$MENU" __index
  assert_output --partial "split vertical"
}

@test "index skips table rows that are not bindings" {
  run "$MENU" __index
  refute_output --partial "begin selection"
}

@test "index survives a missing tmux card" {
  rm "$XDG_DATA_HOME/workflows/tmux-commands.md"
  run "$MENU" __index
  assert_success
}
