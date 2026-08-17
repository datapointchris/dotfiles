---
icon: material/lightbulb
---

# Learnings

Each learning is one bug, gotcha, or measured lesson from dotfiles development.

## Search by the symptom, not by the tool

Reach for these before diagnosing a broken install, a tool that stopped working, or an
error that makes no sense. A learning quotes the error text verbatim wherever there is
one, so the string on screen is the string to search for:

```bash
rg -i "no route to host" docs/learnings/
```

The site search above covers the same ground from a browser.
