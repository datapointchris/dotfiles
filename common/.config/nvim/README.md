# Neovim Config

## Shit to Sort Later

### Profiling

Run these commands:

```bash
:profile start profile.log
:profile func *
:profile file *
# At this point do slow actions
:profile pause
:noautocmd qall!
```
