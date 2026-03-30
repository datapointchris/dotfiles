# Neovim Config

## Profiling

Profile slow actions by capturing function and file timing:

```bash
:profile start profile.log
:profile func *
:profile file *
" At this point do slow actions
:profile pause
:noautocmd qall!
```
