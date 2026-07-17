---
tags: [forge, syncer, repos, fan-out, maintenance, cross-project, recipe]
---

# apply a change across ALL repos (syncer-clean → dry-run → fan out → verify)

```bash
# GOAL: run the same command or edit in every repo — bump a dependency, fix a
# config, run a git command everywhere — without cd-ing through them by hand and
# without stranding work on this machine. forge fans out over the repo list
# syncer tracks, so the two bookend the operation.

# 1. START CLEAN — so the fan-out's changes are distinguishable from stray dirt
syncer                    # every repo committed + pushed? If not, deal with it
                          # FIRST. Fanning out onto a dirty tree mixes your new
                          # change with whatever was already uncommitted there.

# 2. PREVIEW — which repos will this touch?
forge exec -n -- git status --short    # -n/--dry-run: names the repos, runs
                                       # nothing. ALWAYS do this before a mutating
                                       # command. (everything after -- is the
                                       # command fanned out — the -- is required.)

# 3. FAN OUT — pick the form that matches the job
forge exec -- git pull                 # one-off inline command, every repo
forge exec -F relate,nomad -- <cmd>    # -F/--filter: only these repos
forge dies run <name>                  # a REUSABLE maintenance script (a "die").
                                       # If you'll ever run it again, it belongs
                                       # here — never hand-edit a per-repo script.

# 4. VERIFY — nothing left stranded
syncer                    # confirm the fan-out's commits actually pushed in
                          # every repo. This is why syncer bookends the workflow.
```

## The whole thing in two lines

```bash
syncer  →  forge exec -n -- <cmd>   # clean + preview
forge exec -- <cmd>  (or forge dies run <name>)  →  syncer   # apply + verify
```

## Gotchas

```bash
# - The `--` is not optional: `forge exec -- git log` — it separates forge's own
#   flags from the command. Forget it and forge tries to parse `git` as a flag.
# - `-n` first, every time the command writes. The preview is cheap; undoing a
#   bad fan-out across 15 repos is not.
# - One-off vs reusable: inline `exec --` for a throwaway; promote anything you'd
#   run twice into a die (`forge dies run`) so it's tracked and repeatable.
# - forge only knows the repos SYNCER tracks. Added/removed a project and it's
#   not in the fan-out? Reconcile the list with `syncer issues` first.
```

Related: `synthesize-a-batch-of-sources` (another "drive many things at once"
tool). For where each project *stands* rather than acting on them: `forge status`.
