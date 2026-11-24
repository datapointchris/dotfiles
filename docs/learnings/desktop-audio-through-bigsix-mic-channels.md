# Desktop Audio Through a Mixer's Mic Channels

## Problem

Music from the desktop to an SSL BiG SiX drove channels 1 and 2's meters to the top and clipped
audibly at 80% sink volume, while the room stayed quiet. Those two channels also read lower than the
stereo channels for the same source.

PipeWire's multichannel sink maps a stereo stream's FL and FR onto AUX0 and AUX1. The BiG SiX feeds
USB returns 1-4 into mono channels 1-4, at unity after the mic preamp. So the music ran through two
mono strips, with their EQ, dynamics, meter, fader and pan. A mono channel panned center sends
-4.5 dB to each side of the main bus. Two centered channels therefore play the music in mono and
4.5 dB down.

Every stage in the chain clips at its own ceiling, and the room's loudness is the sum of every gain.
With the gain early (the sink volume) and the attenuation late (the speakers' own volume), an early
stage clips while the room is quiet. The console's outputs are pro level and swing past +24 dBu. A
consumer RCA input, such as a powered desktop speaker's, usually tops out near 2 V (about +8 dBu).

## Solution

`configs/os/linux/.config/pipewire/pipewire.conf.d/50-desktop-audio-to-bigsix-ext2.conf` adds a
stereo "BiG SiX EXT 2" sink that feeds AUX14 and AUX15. Those are USB returns 15/16, which the
console routes to EXT 2 in its monitor section, past every channel strip. On the console, press the
USB switch for EXT 2 beside TALK LEVEL, select EXT 2 as a monitor source, and set the EXT 2 level to
its unity detent.

Make the new sink the default, and pin the multichannel sink at 100% so the EXT 2 sink's volume is
the only software level:

```bash
pactl set-default-sink bigsix_ext2
pactl set-sink-volume alsa_output.usb-Solid_State_Logic_BiG_SiX-00.multichannel-output 100%
```

WirePlumber keeps both in `~/.local/state/wireplumber/`, which nothing here deploys, so a rebuilt
machine runs them again. Take loudness from the end of the chain: keep the desktop volume moderate,
and raise the monitor level or the speakers.

## Key Learnings

- USB returns 5-12 reach the stereo channels before their Trim, at unity on its detent. Returns 13/14
  and 15/16 reach EXT 1 and EXT 2. SSL's guide sends a Mac's system audio to EXT 2 the same way.
- The converters are aligned so 0 dBFS = +24 dBu. The channel meter's top LED is +24 dBu, and the
  strip clips at +27 dBu. The meter reads after EQ and dynamics, before the fader.
- The loopback leaves out `node.dont-fallback`. With it, WirePlumber never relinks the stream once
  the console disappears, so EXT 2 stays silent after a power cycle until PipeWire restarts. Without
  it, the stream falls back to another output while the console is off and returns when it is on.
- The same console's hidden USB master volume:
  [A USB Interface Keeps Its Own Master Volume](a-usb-interface-keeps-its-own-master-volume.md).
