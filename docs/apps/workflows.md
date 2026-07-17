---
icon: material/book-open-variant
---

# Workflows

Personal process reference — a searchable deck of Markdown cards for multi-step procedures and tool cheat sheets that are easy to forget between uses. Cards render in the terminal via the `workflows` CLI.

```bash
workflows                       # help
workflows <term>                # search cards by name and tags
workflows list                  # list every card
workflows show <name>           # render one card
workflows new <name>            # create a card and open in $EDITOR
```

Cards live in `~/.local/share/workflows/` (symlinked from `configs/common/.local/share/workflows/` in this repo). The renderer strips YAML frontmatter, so the `tags:` line is for search only and never shows on screen.

## Two kinds of card

The value of the deck depends on picking the right shape for what you are capturing. A card answers one of two questions, and which one determines its name, tags, and structure.

**Reference cards** answer *"what are the commands for tool X"*. They are flat cheat sheets — one tool's commands and keybindings, grouped by section (`ripgrep-patterns`, `neovim-motions`, `git-log`). Name them after the tool. Reach for a reference card when you know the tool and just need to jog your memory on its flags.

A reference card earns its place only when it beats running `--help`. That means the tool's useful surface is large *and* forgettable *and* hidden — `eza`, whose best flags live behind the `ls` alias, or `git`, whose subcommands sprawl. Do **not** write a reference card that merely regroups a tool's `--help`: it goes stale against the tool and duplicates what `menu`/`toolbox` already surface. This rules out reference cards for your own tools entirely — they are self-documenting, so capture them as *workflows* (below) or not at all.

**Recipe cards** answer *"how do I accomplish goal Y"*. They carry a single goal through several tools start to finish, with the exact keys inline at each step (`neovim-refactor-across-files` walks grep → quickfix → mass edit). Name them after the **goal**, verb-first, so the card surfaces when you search by what you are trying to do rather than by a tool you might not remember is involved. Tag them `recipe` plus every term you might reach for.

The distinction exists because a multi-tool sequence has no natural home among single-tool references. Before recipe cards, remembering "search the project and rename the result in every file" meant reassembling the steps from the telescope card, the quickfix card, and the search-replace card every time. A recipe collapses that into one lookup. The test: if finishing the task makes you jump between tools, it is a recipe — write it as an ordered sequence, not a command dump.

## Adding a card

Create cards two ways. `workflows new <name>` scaffolds a file and opens it in `$EDITOR` for hand-authoring. Or, after working through something with Claude Code, the `/add-to-workflows` skill extracts what was learned into a correctly-formatted card and commits it — that skill encodes the reference-vs-recipe convention above so generated cards land in the right shape.

Keep cards to roughly one terminal screen (around 60 lines). Enough to be a useful jog, not so much that the card becomes documentation — long-form explanation belongs here in `docs/`, not on a card.
