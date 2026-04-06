# python callbacks — inversion of control for progress and hooks

Decouple "what happens" from "how it's reported" by passing a callback from
the caller into the worker. The worker calls it at stage boundaries; the caller
decides what to do with the message.

## The pattern

```python
from collections.abc import Callable

# Worker: defines the contract, knows nothing about the UI
def do_work(
    url: str,
    on_progress: Callable[[str], None] | None = None,  # optional hook
) -> Result:
    data = extract(url)
    if on_progress:                                     # guard: callback is optional
        on_progress(f'Extracted: {len(data):,} chars')

    result = analyze(data)
    if on_progress:
        on_progress('Analysis complete')

    return result

# Caller A: Rich spinner — method reference is enough
with console.status('Working...') as status:
    result = do_work(url, on_progress=status.update)    # status.update(str) -> None

# Caller B: Rich progress bar — lambda adds formatting
result = do_work(
    url,
    on_progress=lambda msg: progress.update(task, description=f'[dim]{msg}[/dim]'),
)

# Caller C: no UI (tests, scripts, MCP) — just omit it
result = do_work(url)                                   # on_progress=None, guards skip
```

## When to use vs alternatives

```text
Callback (this)       Few call sites, simple string messages, optional reporting
                      Right weight for 2-5 status updates in a function

Logging + handler     Operational logs that should always run, not UX feedback
                      Wrong: mixes "user should see this" with "debug this later"

Return intermediates  Forces caller to orchestrate multi-step flow
                      Use when caller actually needs intermediate values

Event emitter         Many listeners, dynamic subscribe/unsubscribe
                      Overkill for "tell the UI what stage I'm on"

Generator/yield       Caller drives iteration, worker pauses between steps
                      Use when caller controls pacing (streaming, pagination)
```

## Gotchas

```python
# Lambda in a loop — late binding captures the variable, not the value
for task in tasks:
    cb = lambda msg: progress.update(task, description=msg)    # BUG: all share last task
    cb = lambda msg, t=task: progress.update(t, description=msg)  # FIX: default arg captures

# Method references: bound methods already match Callable[[str], None]
status.update           # ✓ pass directly, no lambda needed
lambda msg: status.update(msg)  # ✗ refurb/FURB111 flags this as unnecessary wrapper
```
