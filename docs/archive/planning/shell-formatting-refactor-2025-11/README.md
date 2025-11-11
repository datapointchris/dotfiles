# Planning Directory

This directory contains planning documents for various features and improvements to the dotfiles system.

## Planning Methodology

Planning documents follow an iterative, numbered approach that preserves the decision-making process and research history.

### Structure

```
.planning/
├── README.md (this file)
└── {feature-name}/
    ├── 01-initial_planning.md
    ├── 02-refined_approach.md
    ├── 03-implementation_details.md
    └── ...
```

### Document Naming Convention

Each planning directory (e.g., `universal-menu/`) contains numbered markdown files:

- **Format:** `{number}-{descriptive_name}.md`
- **Example:** `01-initial_planning.md`, `02-menu_choice_refinement.md`
- **Number:** Zero-padded two digits (01, 02, 03, etc.)
- **Name:** Descriptive, lowercase with underscores

### Document Structure

**First Document (01):**
- Problem statement and goals
- Current state assessment
- Initial research
- Proposed solutions with tradeoffs
- Open questions

**Subsequent Documents (02+):**
- **Top Section:** Summary of new information and decisions made since previous document
- **Main Content:** New research, refined plans, updated recommendations
- **Conversational Tone:** Written to be readable and maintain context

### Highest Number = Most Current

The document with the highest number in each directory is the most recent and represents the current plan. Lower-numbered documents are historical and preserve the evolution of thinking.

### Why This Approach

1. **Traceability:** Can trace back through decision history
2. **Alternatives:** Can review alternatives considered but not chosen
3. **Context:** Understand why decisions were made
4. **Iteration:** Easy to refine without losing previous thinking
5. **Preservation:** Original research remains accessible

## Active Planning Projects

*No active planning projects currently. All planning documents are archived in `docs/archive/planning/` once implementation is complete.*

## Note on Git

This `.planning/` directory is gitignored. Planning documents are:
- Temporary working documents
- Contain brainstorming and alternatives
- May include paths not taken
- Specific to local development workflow

Once a plan is finalized and implemented, relevant documentation should be added to the main `docs/` directory for permanent reference.
