# A USB Interface Keeps Its Own Master Volume

## Problem

Audio from the desktop to an SSL BiG SiX played, but barely. The console's meters did not light
on the USB return, and with the console's controls and the speakers at full it was still quiet.
The PipeWire sink sat at 0.80, about -5.8 dB, which is not low enough to explain it.

`amixer` showed two playback controls with one name. The second is the USB feature unit's
master, and it was cutting 43 dB from every USB channel:

```text
$ amixer -c SiX contents
numid=3,iface=MIXER,name='BiG SiX  Playback Volume'
  : values=127,127,127,127,127,127,127,127,127,127,127,127,127,127,127,127
numid=4,iface=MIXER,name='BiG SiX  Playback Volume',index=1
  : values=84
  | dBminmax-min=-127.00dB,max=0.00dB
```

## Solution

Pin the master at 0 dB and store it. `alsa-restore` reapplies the stored state at boot, and its
udev rule reapplies it whenever the card is plugged in:

```bash
amixer -c SiX cset numid=4 127
sudo alsactl store
```

Turn the console and speakers down before the first command, because it raises the output 43 dB
in one step. Then set the level with the PipeWire volume and gain-stage on the console.

## Key Learnings

- `snd-usb-audio` builds the per-channel controls first and the master second. So the master is
  the `index=1` control with one `Mono` channel, and it is easy to miss beside the 16 at 0 dB.
- PipeWire never writes this control. The BiG SiX's "Multichannel Duplex" profile has no
  hardware volume route, so a sink volume change leaves `numid=4` where it was.
- The value lives in the device, which has its own power supply. Moving the USB cable to another
  host carries over whatever level the last host set. macOS drives this control from its output
  volume slider.
- `/var/lib/alsa/asound.state` is machine state that nothing here deploys. A rebuilt machine
  runs both commands again.
- The ORA by Kanto had the opposite fault, a control that lies about its range:
  [The ORA by Kanto Volume Drop-in](usb-dac-lies-about-its-volume-range.md).
