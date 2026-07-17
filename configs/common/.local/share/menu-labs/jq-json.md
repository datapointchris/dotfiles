---
tags: [jq, json, query, data]
cadence: 1mo
---

# Query and reshape JSON with jq

> `jq` turns "dig through this JSON" into a one-liner. This Lab drills selecting,
> filtering, mapping, and aggregating on a small document.

## Setup

```bash
LAB=$(mktemp -d) && cd "$LAB"
cat > data.json <<'EOF'
{
  "team": "platform",
  "members": [
    {"name": "Ada", "role": "lead", "active": true,  "commits": 120},
    {"name": "Ben", "role": "dev",  "active": false, "commits": 45},
    {"name": "Cy",  "role": "dev",  "active": true,  "commits": 80}
  ]
}
EOF
```

## Steps

1. **Pull a field.** `jq '.team' data.json`
   - Expect: `"platform"`.
   - Why: a filter is a path — `.` is the input, `.team` indexes the object. Add
     `-r` for raw output without the quotes.

2. **Index an array.** `jq '.members[0].name' data.json`
   - Expect: `"Ada"`.
   - Why: `[0]` indexes one element; `.members[]` would stream every element.

3. **Map to one field.** `jq '.members[].name' data.json`
   - Expect: each name on its own line.
   - Why: `.members[]` iterates and the trailing `.name` applies to each. Wrap in
     `[ ... ]` to collect back into an array.

4. **Filter with select.** `jq '.members[] | select(.active)' data.json`
   - Expect: only Ada and Cy.
   - Why: `select(cond)` keeps inputs where the condition holds; `|` pipes each
     member into it. Try `select(.commits > 50)`.

5. **Reshape objects.** `jq '.members | map({(.name): .commits})' data.json`
   - Expect: `[{"Ada":120},{"Ben":45},{"Cy":80}]`.
   - Why: `map(f)` transforms each element; `{(.name): .commits}` builds a new
     object with a *computed* key (the parentheses make `.name` the key).

6. **Aggregate.** `jq '[.members[].commits] | add' data.json`
   - Expect: `245`.
   - Why: collect the commits into an array, then `add` sums it. `length`, `min`,
     `max`, `group_by` compose the same way.

## The whole thing in one breath

```bash
jq -r '.members[] | select(.active) | .name' data.json   # active members, raw
jq '[.members[].commits] | add' data.json                # total commits
```
