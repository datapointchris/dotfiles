---
icon: material/monitor-multiple
---

# Work Monitor

Route the Arch box's spare HDMI output to the work desk's secondary monitor, on demand, without letting Hyprland treat it as a permanent second display.

Arch Linux only.

## Quick Start

```bash
work-monitor           # Toggle the output
work-monitor on        # Enable and switch to workspace W
work-monitor off       # Disable
work-monitor status    # Report current state
```

Bound to ++super+ctrl+w++. Workspace W is reachable with ++super+w++, and ++super+shift+w++ moves the focused window there.

## The Problem This Solves

The personal desk and the work desk sit far enough apart that both screens cannot be read at once. Debugging a work WSL problem from the personal desk therefore means memorising error output and carrying it across the room. Running a cable from the Arch box to the work desk's spare monitor input removes that, and it does so over a pure video path — nothing crosses the corporate network.

The obstacle is what happens the rest of the time. Hyprland's catch-all `monitor = , preferred, auto, 1` rule adopts any output that appears, so a permanently connected second monitor means workspaces spread across two desks and windows open on a panel that is usually showing the work laptop instead.

Leaving the cable plugged in and letting the output come and go on its own does not help either. When the Dell switches to another input it de-asserts hotplug detect, so the source sees a genuine disconnect: Hyprland tears the layout down, migrates workspaces, and rebuilds on reconnect. That reshuffling is the actual complaint, and no display setting prevents it, because from the compositor's point of view the monitor really did disappear.

## How It Works

The output is declared disabled in `conf/monitors.conf`, after the catch-all so it overrides it. A disabled output is not a monitor at all — Hyprland assigns it no workspaces and nothing can open on it, so the default state is a clean single-monitor setup regardless of what the cable is doing.

`work-monitor on` applies a live `monitor` rule with `hyprctl keyword`, which enables the output for that session only. Workspace W is bound to the connector in `conf/workspaces.conf`, so it lands there and nothing else moves. `work-monitor off` re-disables it, and any windows still on W migrate back to the 43".

Because the rule is applied at runtime and the config default is `disable`, a Hyprland reload always returns to the single-monitor state.

Whether the output is currently on is tracked in `$XDG_STATE_HOME/work-monitor/enabled` rather than read back from `hyprctl monitors`. This matters more than it looks: while the Dell is showing the work laptop, hotplug detect is dropped and an enabled output does not appear in that list at all. Querying Hyprland would therefore report "off" whenever the monitor is pointed elsewhere — which is precisely when the toggle needs to work — and pressing the key would re-enable instead of disabling.

The one gap is a config reload while the output is on: `hyprctl reload` restores the `disable` rule but leaves the state file, so the next toggle reads as "turn it off" when it is already off. Press it twice, or run `work-monitor off` to resync. Both are harmless and idempotent.

## Configuration

Defaults suit the Minisforum, whose 43" runs on `DP-4`, leaving the HDMI connectors free. Override with environment variables when the hardware changes:

| Variable | Default | Purpose |
|---|---|---|
| `WORK_MONITOR_OUTPUT` | `HDMI-A-1` | Connector name from `hyprctl monitors all` |
| `WORK_MONITOR_MODE` | `preferred` | Set explicitly when a long cheap cable cannot hold 4K60 |
| `WORK_MONITOR_POSITION` | `auto-right` | Placement relative to the 43" |
| `WORK_MONITOR_SCALE` | `1` | |

Confirm the connector name once, with the cable plugged in and the monitor switched to that input:

```bash
hyprctl monitors all -j | jq -r '.[].name'
```

If it reports `HDMI-A-2`, change the name in `conf/monitors.conf`, `conf/workspaces.conf`, and the script default together.

A cheap cable at that length may negotiate 4K60 and then fail to sync. Drop the mode rather than replacing hardware — `WORK_MONITOR_MODE=3840x2160@30` first, then `1920x1080@60`. Either is fine for glancing at error output.

## Monitor Side

Turn **Auto Select** off in the Dell's OSD. Left on, it jumps to the Arch box the moment that output goes live, pulling the browser and chat off screen mid-work.
