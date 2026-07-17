---
tags: [pre-commit, git, hooks, stages, default_stages, linting]
---

# pre-commit stages — controlling which git hook fires each hook

A "stage" = a git hook type. `pre-commit install -t <type>` writes that git hook.
A pre-commit hook runs at a stage if that stage is in its effective stages list.
Effective = per-hook `stages:` if set, else top-level `default_stages:`, else ALL stages.
That last fallback is the footgun: an unrestricted hook runs at EVERY installed type.

```bash
# The stages (git hook types) pre-commit knows
pre-commit               # staged files, before commit is created   (the 99% case)
prepare-commit-msg       # edit/generate the message pre-editor
commit-msg               # validate the finished message            (conventional commits)
post-commit              # after commit lands — side effects, stats  (never blocks)
pre-push                 # before push — expensive suites
post-merge / post-checkout / post-rewrite / manual
```

```yaml
# Top of config: pin the default so unrestricted hooks stay at pre-commit only
default_stages: [pre-commit]      # <-- without this, hooks with no stages: run everywhere

repos:
  - repo: https://github.com/compilerla/conventional-pre-commit
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]      # explicit per-hook stage OVERRIDES default_stages
  - repo: local
    hooks:
      - id: ruff-check            # no stages: -> inherits default_stages [pre-commit]
      - id: devstats-collect
        stages: [post-commit]     # runs after commit, does not block it
```

```bash
# Install the hook types your config actually uses (each is a separate git hook file)
pre-commit install -t pre-commit -t commit-msg -t prepare-commit-msg
pre-commit install --install-hooks   # also pre-fetch hook environments
ls .git/hooks/                       # verify which types are installed

# Test one stage without a real commit (the only reliable repro)
pre-commit run --all-files                                    # pre-commit stage
pre-commit run --hook-stage commit-msg --commit-msg-filename <(echo "feat: x")
# NOTE: pre-commit refuses to run if .pre-commit-config.yaml is unstaged -> git add it first
```

## The classic bug: hooks firing 2-3x per commit

No `default_stages` + `pre-commit install -t pre-commit -t prepare-commit-msg -t commit-msg`
=> every stage-less lint hook (ruff, codespell, bandit…) runs once per installed type.
Fix: add `default_stages: [pre-commit]`; give only the genuinely staged hooks an explicit
`stages:`. Verify with `pre-commit run --hook-stage commit-msg …` — only the msg hook fires.

## Best practice / industry norm

```text
default_stages: [pre-commit]     top-level, in nearly every real-world config
per-hook stages: [pre-commit]    the default_stages line makes this redundant — drop it
stages: [commit-msg]             ONLY on commit-msg validators (commitizen, conventional)
stages: [pre-push]               heavy/slow hooks (full test suite, integration)
stages: [post-commit]            metrics/notifications that must not block the commit
```

Rule of thumb: set `default_stages: [pre-commit]` once, then add an explicit `stages:` only
to the handful of hooks that must run somewhere else. Anything else is the multi-fire bug.
