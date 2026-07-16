---
tags: [tmux, ssh, remote, nested, multiplexer]
---

# tmux nested over SSH — local panes + a persistent remote session

Nest **only when the remote session must survive a disconnect** (SSH drops → plain
shell dies, tmux session keeps running → `tmux attach` to resume). For pane layout
alone, split in local tmux and SSH plainly — no remote tmux, no nesting.

```text
Local tmux (prefix C-Space)
├── pane 1 → ssh remote → tmux attach   # nested: survives disconnect
└── pane 2 → local shell / filesystem   # plain local pane
```

## Prefix collision — the one gotcha

Both tmux servers grab the prefix (this config: `C-Space`). **Outer (local) wins a
single press. Inner (remote) needs the prefix twice** — the second is passed through
by `bind C-Space send-prefix` (already set in tmux.conf).

| Command…            | Keys                  | Example (split)      |
| ------------------- | --------------------- | -------------------- |
| Outer (local) tmux  | `C-Space` key         | `C-Space -`          |
| Inner (remote) tmux | `C-Space C-Space` key | `C-Space C-Space -`  |
| Detach remote       | `C-Space C-Space d`   | remote keeps running |
| Detach local        | `C-Space d`           | —                    |

## Auto-color — remote sessions pick up the theme's red (already implemented)

The `theme` CLI generates a `REMOTE / SSH INDICATOR` block into `themes/current.conf`
(see `lib/generators/tmux.sh`): when `$SSH_CONNECTION` is set (this tmux started from
an SSH shell), it recolors the host badge, active window, active pane border, and the
pane path using the theme's own `diagnostic_error` red — the background stays `base00`
so it still reads as the current theme. Any box you SSH into colors itself; nothing to
configure per host, and switching themes re-derives the red.

- `$SSH_CONNECTION` is the signal, **not** `$TMUX`: `$TMUX` only catches same-host
  tmux-in-tmux and doesn't survive the SSH hop.
- Read from the server's startup environment, so it fires on the normal
  `ssh box -t 'tmux attach || tmux new'` flow. A server first started detached
  outside SSH (systemd) won't color until restarted.
- It's part of the generated theme, so `theme apply <name>` regenerates it to match
  the new palette.

## Cleaner alternative — different remote prefix (no double-tap)

```tmux
# In the REMOTE's ~/.tmux.conf: local=C-Space, remote=C-a, single press each
set -g prefix C-a
bind C-a send-prefix
```

## Reconnect / expected behavior

```bash
ssh chris@10.0.20.18 -t 'tmux attach || tmux new'   # attach if exists, else create
```

- Two status bars stack (outer above inner) — the red remote bar vs themed local bar
  disambiguates at a glance.
- Copy/scroll mode is per-tmux: `C-Space [` scrolls local, `C-Space C-Space [` remote.
- 256-color/RGB already forced by `default-terminal` + `terminal-features` in the conf.
