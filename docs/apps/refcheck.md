---
icon: material/check-all
---

# Refcheck

Reference validator for codebases — finds broken `source`/`bash` targets, stale paths left behind by a refactor, and relative paths that only resolve from one working directory. A standalone Python project: **[datapointchris/refcheck](https://github.com/datapointchris/refcheck)** is the source of truth for the full flag reference, output format, and configuration (or run `refcheck --help`).

## In this system

- **Install** — `packages.yml` under `git_uv_tools`, installed by `src/dotfiles/providers/uvtool.py`, pinned to its newest release tag (see `install/common/lib/uv-git-tools.sh` for why the pin is required). The entry point lands in `~/.local/bin`. Update with `refcheck --update`, or with the rest of the fleet through `task update`.
- **Why it exists here** — it was written against this repo. Dotfiles is thousands of shell files that `source` each other through `$DOTFILES_DIR` and `$SCRIPT_DIR`, where a moved file breaks a reference that no linter checks and only a full e2e run surfaces. `refcheck` resolves those variables and validates the target in seconds.
- **Fixtures** — `tests/apps/fixtures/refcheck-variables/` and `refcheck-fragile-cwd/` hold deliberately broken scripts, kept as a live target to check the tool still catches what it claims. They are excluded from a normal run; reach them with `refcheck --test-mode tests/apps/fixtures/`.
- **Config** — `~/.config/refcheck/config.toml` and the learned per-repo rules under `~/.config/refcheck/repos/` are runtime state, not dotfiles-managed.

## See Also

- `tests/apps/refcheck-validation-original-issues.md` — the four original path bugs the tool was built to catch, and which of them it does
- [Toolbox](toolbox.md) — tool discovery across the installed toolchain
