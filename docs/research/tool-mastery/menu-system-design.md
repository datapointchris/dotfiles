# Menu System Design

How the `menu` discovery system is designed and the decisions behind it — the
design-of-record for the built system. The research that motivated it lives
alongside in this section, chiefly [Consolidation Architecture](consolidation-architecture.md)
and [Discovery & Terminal Docs](discovery-and-terminal-docs.md).

## The problem

~120 registered tools + 32 workflow cards + 11 skills, and it's easy to forget
they exist or how to combine them. Two orthogonal needs:

- **Find (spatial):** "where is the thing I need right now?" → `menu`
- **Review (temporal):** "what should I revisit / run / practice on a cadence?" → `menu review`

Find serves review: locating a tool once doesn't build retention; scheduled
return does.

## Architecture: a registry federation with a thin composer

Every collection is a **registry** — a store of things with a searchable index.
`menu` is a thin **composer** above them: it federates the collections into one
index and delegates all display back to each collection's own tool. menu owns no
content.

```text
menu  (thin composer: search + delegate)
├── tools      → toolbox    → ~/dev/tools.yml               (hand-curated; tools/scripts/functions/aliases/vetted externals)
├── workflows  → workflows  → ~/.local/share/workflows/*.md (tagged markdown cards)
└── skills     → (auto)     → ~/.claude/skills/*/SKILL.md   (self-describing frontmatter, global only)
```

### Settled design rules

- **One registry is the vetted allow-list.** menu searches only your own
  collections — never tldr/cheat's universe. No "30 backup tools you don't have"
  noise.
- **Graduated entry depth.** Rich entries for your own tools (full metadata);
  thin pointers for vetted externals like `scp` (content comes from lenses);
  functions/aliases live in the tools registry too, findable alongside tools.
- **Metadata lives once; content is pulled live.** The registry stores *why you'd
  want it / how to find it* (description, tags, why_use). The actual *what it is*
  comes live from `--help` (tools), `type` (aliases/functions), or the tldr/cheat
  page. `toolbox check` guards coverage (registry ↔ PATH ↔ disk) so nothing lives
  in two places and drifts.
- **Tags are the discovery contract.** Search is biased to name+tags; a good tag
  is what makes something findable. Missing a result → add a tag, don't change
  menu.

## The lens model (the full view)

Pressing Enter on a picker result assembles everything known about that *subject*
from whichever lenses have it, in priority order, showing only the sections that
exist:

`--help` (own tools) → toolbox metadata → tldr → cheat → workflow → skill

- `backmeup` (own tool) → help + toolbox.
- `bat` (external) → toolbox + tldr + cheat.
- `git-stash` (workflow) → tldr + workflow.
- `capture-note` (skill) → skill.

The HELP lens fires only for your own tools that resolve on PATH (registry
`category: custom-tools`), run under `timeout 5`; running `--help` on an arbitrary
external command is unsafe, so externals lean on tldr/cheat.

## Two verbs, not three

- **`menu [term]`** is the picker, and Enter opens the full view — find and show
  are one motion.
- **`menu review`** (no argument) is the temporal half: the cadence-due list.

There is deliberately no `show` verb and no `review <topic>` study page. The
collapse happened because find-vs-show was too subtle a distinction to remember.
Search is **WYSIWYG**: name + description + tags live in the one displayed field,
and that is exactly what fzf searches — what you see is what matches.

## The review register

The cadence register is implemented in **Python** (`apps/common/menu-review`, a
uv single-file script; `menu review` delegates to it via `exec`). Bash was tried
first and reversed mid-build: the register is data + dates + state, exactly where
bash fights you (IFS collapses empty columns, epoch math is manual, sorting is
error-prone). Python's `datetime`/`json` make it trivial and correct.

Two files, a clean config/state split:

- `~/dev/review.yml` — declarative, hand-edited, **read-only to the tool**
  (python-yq and pyyaml both strip comments on write, so config must never be
  machine-written).
- `~/dev/review-state.json` — the `last_done` map, written by `done`.

`next_due = last_done + cadence` is **derived, not stored**. Subcommands:
`menu review` (due list), `list`, `done <id>`, `edit`. Review items include
skills that are themselves review cadences (`audit-repo-docs`, `review-fleet`).

## Future directions

- **tool-usage curation loop** — gently surface frequently-used commands not yet
  in the registry ("you use `scp` 40×, add it?"). A pull-report, never a nag.
- **Semantic search via `indy`** — a future safety net over the registries for
  conceptual queries the tag index misses.
