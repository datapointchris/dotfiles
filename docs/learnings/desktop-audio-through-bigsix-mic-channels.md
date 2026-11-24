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

`configs/os/linux/.config/pipewire/pipewire.conf.d/50-desktop-audio-to-bigsix-stereo-channel.conf`
adds a stereo "BiG SiX Stereo 5/6" sink that feeds AUX4 and AUX5. Those are USB returns 5/6, which
reach the first stereo channel before its Trim. The music then shows on that channel's stereo meter
and runs through its EQ, balance and fader into the main bus and its G-Series bus compressor. On the
console, press the USB switch at the top of stereo channel 5/6 and set its Trim to the unity detent.

Make the new sink the default, and pin the multichannel sink at 100% so the new sink's volume is the
only software level:

```bash
pactl set-default-sink bigsix_stereo_5_6
pactl set-sink-volume alsa_output.usb-Solid_State_Logic_BiG_SiX-00.multichannel-output 100%
```

WirePlumber keeps both in `~/.local/state/wireplumber/`, which nothing here deploys, so a rebuilt
machine runs them again. The desktop volume now sets how hard the bus compressor works, so set it
once and take loudness from the fader, the monitor level or the speakers.

## Key Learnings

- Returns 13/14 and 15/16 reach EXT 1 and EXT 2 in the monitor section, past every channel strip.
  `audio.position = [ AUX14 AUX15 ]` is the route for listening with no processing. SSL's guide
  sends a Mac's system audio there.
- Only the four mono channels have dynamics. Two mono channels panned hard left and right keep the
  stereo, but their compressors act on each side alone and pull the image. The bus compressor is
  one stereo unit across the main mix.
- The converters are aligned so 0 dBFS = +24 dBu. The channel meter's top LED is +24 dBu, and the
  strip clips at +27 dBu. The meter reads after EQ and dynamics, before the fader.
- The loopback leaves out `node.dont-fallback`. With it, WirePlumber never relinks the stream once
  the console disappears, so the output stays silent after a power cycle until PipeWire restarts.
  Without it, the stream falls back to another output while the console is off and returns when it
  is on.
- The same console's hidden USB master volume:
  [A USB Interface Keeps Its Own Master Volume](a-usb-interface-keeps-its-own-master-volume.md).
