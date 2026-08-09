# A USB DAC That Lies About Its Volume Range

## Problem

The ORA by Kanto (USB) had a volume slider whose lower half did nothing: anything
below roughly 50% was silent, and every step above it jumped a lot, as though the
scale had been cut in half. Waybar's percentage was therefore meaningless.

The device's USB descriptor is the cause:

```text
/proc/asound/card4/usbmixer
  Control: name="PCM Playback Volume"
    Volume: min=0, max=4096, dBmin=0, dBmax=1600
```

It declares its range as **0 dB to +16 dB** — gain only, no attenuation, with its
minimum position claimed to be unity. PipeWire's ACP layer believes the descriptor,
anchors the sink's 100% to the hardware maximum, and so has to fit the entire
control into the top 16 dB of the slider:

```text
pactl list sinks →  Base Volume: 35466 /  54% / -16.00 dB
```

Everything below 54% clamps the control to raw 0, which on this device is actually
silence rather than the unity gain it advertises. The arithmetic reproduces the
observed state exactly: slider 60% → cubic amplitude 0.6³ = 0.216 → −13.31 dB →
hardware 16 − 13.31 = +2.69 dB → raw 2.69 × 256 = 689, and `amixer -c 4 sget PCM`
read `689 [17%] [2.69dB]`. `pw-dump` confirmed `softVolumes: [1.0, 1.0]` — every bit
of attenuation was riding on that one lying hardware control.

## Solution

Take the hardware control out of the volume path entirely, via a WirePlumber device
rule (`configs/os/linux/.config/wireplumber/wireplumber.conf.d/50-ora-kanto-volume.conf`):

```text
api.alsa.soft-mixer = true
```

Then pin the ALSA control at its maximum so software has the full range, and store
it so `alsa-restore` brings it back on boot and on replug:

```bash
amixer -c Kanto sset PCM 100%
sudo alsactl store
```

`api.alsa.ignore-dB = true` was tried first and rejected. It does fix the dead zone
— base volume returns to 100% and the mapping becomes `raw = 4096 × percent` — but
ACP then maps raw linearly against the *percentage*, and this control turns out to
be linear in **amplitude**, not dB. Measured by ear: comfortable listening landed at
15%, and 50%→100% spanned only about 6 dB. That trades a dead lower half for a
useless upper three-quarters.

## Key Learnings

- A USB audio device's declared dB range is a firmware claim, not a measurement.
  `dBmin=0, dBmax=1600` on a device whose minimum is audibly silent is self-
  contradictory, and round hex bounds (0x0000–0x1000) suggest a linear scale the
  author never meant as decibels.
- `Base Volume` in `pactl list sinks` is the tell. Anything other than
  `65536 / 100% / 0.00 dB` means part of the slider is unreachable, and the
  percentage it reports is where the dead zone ends.
- `softVolumes: [1.0, 1.0]` in `pw-dump <sink-id>` means no software attenuation is
  being applied, so the hardware control alone determines the taper.
- Distinguish the two fixes by what the device is wrong about. `ignore-dB` keeps
  hardware volume and suits a device whose dB *table* is wrong but whose control is
  well behaved; `soft-mixer` suits one whose control is the wrong shape, because it
  removes the device's curve from the question entirely.
- A sink's monitor source taps the mix *before* hardware volume. It confirms what is
  being sent, never what the speaker does with it — so it cannot characterise a
  hardware volume curve. Without a loopback or a mic, that measurement needs ears.
