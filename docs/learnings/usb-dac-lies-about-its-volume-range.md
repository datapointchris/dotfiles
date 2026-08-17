# The ORA by Kanto Volume Drop-in

The ORA by Kanto (USB) declares a volume range its hardware does not have, so the lower half of
the slider is silent and waybar's percentage means nothing. The fix takes the hardware control out
of the volume path and gives the taper to PipeWire's software curve.

## The drop-in

`configs/os/linux/.config/wireplumber/wireplumber.conf.d/50-ora-kanto-volume.conf` matches the card
by name and sets `api.alsa.soft-mixer = true`. It deploys with the rest of the `os/linux`
coordinate variant, so `dotfiles symlinks apply` is what lands it on a machine.

## Pin the ALSA control and store it

Software owns the taper only while the hardware control sits at its maximum. Pin it, then store it
so `alsa-restore` brings it back on boot and on replug:

```bash
amixer -c Kanto sset PCM 100%
sudo alsactl store
```

That store is machine state, not repo state. `alsactl` writes `/var/lib/alsa/asound.state`, which
nothing here deploys, so both commands run again on a rebuilt machine.

Why the descriptor is wrong, how to spot the same fault on another device, and why
`api.alsa.ignore-dB` was tried and rejected:
[A USB DAC That Lies About Its Volume Range](https://docs.ichrisbirch.com/linux/usb-dac-volume-range/)
on the hub.
