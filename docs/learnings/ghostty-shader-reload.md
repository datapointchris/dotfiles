# Ghostty Custom Shaders Need a Full Relaunch

## Problem

Editing a `custom-shader` GLSL file and reloading the Ghostty config with ++cmd+shift+comma++
appears to do nothing. The old shader keeps rendering, so successive rounds of tuning all look
identical and the effect seems broken rather than unchanged.

This wastes a lot of time, because every symptom points at the shader. The config reloads cleanly,
`ghostty +validate-config` stays silent, the path still resolves, and the file on disk is
demonstrably different — yet the picture never changes.

## Root Cause

Ghostty compiles custom shaders once when the renderer builds its pipeline. Config reload compares
config *values*, and editing the contents of a file the config already points at leaves that value
untouched, so nothing triggers a recompile. Ghostty does not watch shader files for changes.

Two separate limitations compound this, both tracked upstream:

- Shader state is not fully reset on reload ([discussion #10146](https://github.com/ghostty-org/ghostty/discussions/10146))
- Even changing the `custom-shader` value only affects new windows, tabs, and splits, never
  existing surfaces ([discussion #4016](https://github.com/ghostty-org/ghostty/discussions/4016))

## Solution

Quit Ghostty entirely (++cmd+q++) and relaunch. A config reload is not enough for any shader change.

Quitting is safe for tmux work: the tmux server is parented to the init process, not to the
terminal, so quitting kills only the client and detaches the session. `tmux attach` restores
everything, including a running Claude Code session inside a pane. Only processes running in a
Ghostty window *outside* tmux are lost.

## Key Learnings

- Verify a shader change is actually live before drawing conclusions from what it looks like.
  Set a parameter to an absurd value first — if the picture does not change, the pipeline is
  stale and no amount of tuning matters.
- Compile-check GLSL out of band rather than relying on the terminal to report failures. Ghostty
  swallows shader compile errors into the render thread's log, so they never surface as config
  errors. Concatenating Ghostty's uniform block with the shader body and running it through
  `glslc -fshader-stage=fragment` catches syntax and type errors in a second.
- Ghostty resolves `custom-shader` relative paths against the config file's *realpath*, while
  `config-file` resolves against the symlink's directory. A shader stored in this repo therefore
  resolves through the symlink back into the repo, which works on any machine and any clone
  location.
