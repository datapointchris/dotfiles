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

## Auto-color — ssh panes get a red border (host-side, already implemented)

The **local** tmux detects when a pane is running ssh (`pane_current_command == ssh`)
and paints that pane's border the theme's `diagnostic_error` red with a `󰢹 SSH` badge.
It's a conditional in the theme-generated `pane-border-format` (see
`lib/generators/tmux.sh`), so switching themes re-derives the red.

- **Nothing is required on the remote** — detection is local, so a bare box with no
  tmux/theme (e.g. an LXC) still lights up red the moment you ssh into a pane.
- Per-pane: in a split, the ssh pane border is red while the local pane stays normal —
  both visible at once.
- No SSH needed to preview: run `ssh <host>` in any local pane and its border turns red.
- The remote host isn't shown (tmux can't read ssh's args reliably); the badge just
  says `SSH`. `pane-border-status top` (set in tmux.conf) keeps the border visible even
  for a single pane.

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
