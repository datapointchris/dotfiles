# A Pro Console Overdrives a Consumer Speaker Input

## Problem

Desktop music through an SSL BiG SiX into ORA by Kanto speakers distorted from about 65% desktop
volume, and whenever a console fader went above 0, while the room was still quiet. Turning up the
speakers' own knob stayed clean.

The console's outputs are pro level and swing past +24 dBu. The speakers' RCA input is consumer
level, and such an input usually tops out near 2 V, about +8 dBu. Every control ahead of that input
drives it: the desktop volume, Trim, the faders and the monitor level. The speakers' knob sits after
it, so it changes loudness and never causes the clipping. At 65% the music peaked near +8 dBu in the
console, which still had 19 dB of headroom.

The desktop feed first landed on mono mic channels 1 and 2. PipeWire's multichannel sink maps a
stereo stream's FL and FR onto AUX0 and AUX1, which are USB returns 1 and 2. Panned center, each
mono channel sends -4.5 dB to both sides, so the music played in mono and quieter there.

## Solution

The fix is a fixed -18 dB on the desktop feed.
`configs/os/linux/.config/pipewire/pipewire.conf.d/50-desktop-audio-to-bigsix-stereo-channel.conf`
makes the "BiG SiX Stereo 5/6" sink a filter chain with a gain of 0.125. At 100% a full-scale peak
leaves at -18 dBFS, about +6 dBu, under the speakers' input with every fader at 0. The whole desktop
slider is clean, and each 1% step at full loudness is 0.26 dB rather than 0.53 dB at 50%.

Plug the speakers into MAIN MONITOR rather than MAIN, and run the Monitor Level knob at 11, its unity
point. The cut leaves no spare level, so the music turns quiet below 11. Set the speakers' knob
once, to the loudest wanted at 100%, and use the desktop volume from there.

The sink feeds AUX4 and AUX5, USB returns 5/6, which reach the first stereo channel before its Trim.
The music shows on that channel's stereo meter and runs through its EQ, balance and fader into the
main bus and its G-Series bus compressor. On the console, press the USB switch at the top of stereo
channel 5/6 and set its Trim to the unity detent.

Make the new sink the default, and pin the multichannel sink at 100% so the new sink's volume is the
only software level:

```bash
pactl set-default-sink bigsix_stereo_5_6
pactl set-sink-volume alsa_output.usb-Solid_State_Logic_BiG_SiX-00.multichannel-output 100%
```

WirePlumber keeps both in `~/.local/state/wireplumber/`, which nothing here deploys, so a rebuilt
machine runs them again.

## Key Learnings

- The MAIN jacks carry the main bus after its fader, which adds up to +10 dB. The MAIN MONITOR jacks
  follow the Monitor Level knob, which tops out at unity. DIM, CUT and PFL act only on the monitor
  jacks, so speakers on the MAIN jacks ignore all four.
- Returns 13/14 and 15/16 reach EXT 1 and EXT 2 in the monitor section, past every channel strip.
  `audio.position = [ AUX14 AUX15 ]` is the route for listening with no processing.
- Only the four mono channels have dynamics, and each acts on one side alone. The bus compressor is
  one stereo unit across the main mix.
- The converters are aligned so 0 dBFS = +24 dBu. The channel meter's top LED is +24 dBu, and the
  strip clips at +27 dBu.
- The playback side leaves out `node.dont-fallback`. With it, WirePlumber never relinks the stream
  once the console disappears, so the output stays silent after a power cycle until PipeWire
  restarts.
- The `mixer` plugin has eight inputs, so the graph names `pad:In 1` and `pad:Out` itself. Then
  filter-chain copies the one-in, one-out graph once per stereo channel.
- The same console's hidden USB master volume:
  [A USB Interface Keeps Its Own Master Volume](a-usb-interface-keeps-its-own-master-volume.md).
