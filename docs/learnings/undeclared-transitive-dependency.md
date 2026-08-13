# The installed tool had no click, and every local gate passed

## Problem

`dotfiles` stopped running on the machine. Every invocation ended in:

```text
  File "/home/chris/dotfiles/src/dotfiles/refusal.py", line 28, in <module>
    import click
ModuleNotFoundError: No module named 'click'
```

The change that caused it had passed ruff, mypy, the full pytest suite, the
pre-commit gate and four CI jobs, and had been merged.

Two environments, two different typers:

```text
dev venv    typer 0.24.1   Requires-Dist: click>=8.2.1     click 8.3.0 present
tool venv   typer 0.27.1   vendors typer._click, no dep    click absent
```

`pyproject.toml` declares `typer>=0.12.0`, which both satisfy. Nothing declared
`click`. `uv run` resolved the older typer and therefore had click, so every
local check imported it happily; `uv tool install` resolved the newer one, and
the binary on `PATH` could not start.

## Solution

Stop importing it. Nothing click was doing needed click:

- `click.Choice([...])` on an option → annotate the parameter `axes.Arch`. Typer
  renders `<x86_64|arm64>` and rejects anything else with exit 2 from the enum.
- `click.IntRange(1, n)` in a prompt → read an `int` and check the bounds.
- `click.Context` on an overridden `invoke` → leave it untyped. Its type is
  whichever click the installed typer carries, and naming either narrows the
  supertype's parameter on the version that has the other.

`tests/test_dependencies.py` is the guard. It walks the package's AST for
top-level imports, asks `importlib.metadata.packages_distributions()` which
distribution provides each, and fails on any that `[project.dependencies]` does
not name. Re-adding `import click` fails it with
`{'click': ['refusal.py']}`.

## Key Learnings

- **A transitive dependency is one resolution, not a promise.** A library is free
  to vendor or drop a dependency in a minor release, and a range like
  `>=0.12.0` spans both sides of that.
- **`uv run` and `uv tool install` resolve separately.** The dev venv is not a
  preview of the installed tool, so a green suite says nothing about whether the
  shipped binary imports.
- **The cheapest real check is the shipped interpreter.** Running
  `PYTHONPATH=src <tool-venv>/bin/python -c 'from dotfiles.main import app'`
  reproduced it in one command, after the CI matrix had missed it entirely.
- **B008 exempts a call in a default only for immutable builtin annotations.**
  Switching an option to an enum makes it fire; the module-level option singleton
  the file already uses everywhere is the fix, not an ignore.
