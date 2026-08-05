---
icon: material/lightbulb
---

# Learnings

Concise lessons learned from dotfiles development. Each learning captures a specific bug, gotcha, or best practice worth remembering.

Browse learnings in the sidebar navigation. Each focuses on a single problem and solution.

## Searching

Reach for these before diagnosing a broken install, a tool that stopped working, or an error that makes no sense. Search by the symptom rather than by the tool — a learning quotes the error text verbatim wherever there is one, so the string on screen is the string to search for:

```bash
rg -i "no route to host" docs/learnings/
```

The site search above covers the same ground from a browser.

## Format

Learnings follow a concise format (30-50 lines):

1. **Problem**: What went wrong
2. **Solution**: How to do it correctly
3. **Key Learnings**: Bullet points of actionable wisdom
4. **Testing**: Brief example (optional)
5. **Related**: Links to other learnings

## Adding Learnings

Create new learning in `docs/learnings/` when you discover something worth remembering.

Target 30-50 lines total - if longer, it belongs in main documentation not learnings.
