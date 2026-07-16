---
tags: [tmux, ssh, remote, nested, multiplexer]
---

# tmux nested over SSH — local panes + a persistent remote session

Nest **only when the remote session must survive a disconnect** (SSH drops → plain
shell dies, tmux session keeps running → `tmux attach` to resume). For pane layout
alone, split in local tmux and SSH plainly — no remote tmux, no nesting.

```text
Local tmux (prefix Ctrl-b)
├── pane 1 → ssh remote → tmux attach   # nested: survives disconnect
└── pane 2 → local shell / filesystem   # plain local pane
```

## Prefix collision — the one gotcha

Both tmux servers grab `Ctrl-b`. **Outer (local) wins a single press. Inner (remote)
needs the prefix twice.** Double-press works with zero config (`send-prefix` default).

| Command…            | Keys                | Example (split)   |
| ------------------- | ------------------- | ----------------- |
| Outer (local) tmux  | `Ctrl-b` key        | `Ctrl-b %`        |
| Inner (remote) tmux | `Ctrl-b Ctrl-b` key | `Ctrl-b Ctrl-b %` |
| Detach remote       | `Ctrl-b Ctrl-b d`   | remote keeps running |
| Detach local        | `Ctrl-b d`          | —                 |

## Auto-color the remote status bar (so you know which tmux you're driving)

Put in the **remote's** `~/.tmux.conf`. `$SSH_CONNECTION` is set because the remote
tmux started from an SSH shell — the reliable "I'm the nested one" signal.

```tmux
# Distinct bar on any box reached over SSH
if-shell '[ -n "$SSH_CONNECTION" ]' \
  'set -g status-style "bg=colour88 fg=white"'   # dark red = remote

# Per-host color (SSH to several boxes) — branch on hostname
if-shell '[ "$(hostname -s)" = "immich-lxc" ]' \
  'set -g status-style "bg=colour24 fg=white"'
```

`$TMUX` detects only *same-host* tmux-in-tmux; it does NOT survive the SSH hop, so use
`$SSH_CONNECTION` for the remote case. tmux reads config at server start, so the color
is set once when the remote session is first created.

## Cleaner alternative — different remote prefix (no double-tap)

```tmux
# In the remote's ~/.tmux.conf: local=Ctrl-b, remote=Ctrl-a, single press each
set -g prefix C-a
bind C-a send-prefix
```

## Reconnect / expected behavior

```bash
ssh chris@10.0.20.18 -t 'tmux attach || tmux new'   # attach if exists, else create
tmux -2 ...                                          # force 256-color through the hop
```

- Two status bars stack (outer above inner) — normal; the color fix disambiguates.
- Copy/scroll mode is per-tmux: `Ctrl-b [` scrolls local, `Ctrl-b Ctrl-b [` scrolls remote.
