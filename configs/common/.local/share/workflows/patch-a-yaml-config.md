---
tags: [yq, yaml, config, jq, edit, kubernetes, compose, recipe]
---

# patch a YAML config in place (yq: read → set → convert, without hand-editing)

```bash
# GOAL: change a value in a real YAML config — docker-compose, a k8s manifest, a
# CI file — without opening it and fighting indentation, and preserving comments.
# This is the mikefarah yq (v4, Go binary). It is NOT the python yq and NOT jq —
# similar shape, different function set. `expr` is the FIRST arg, file is second.

# 1. READ — confirm the path before you write it
yq '.services.web.image' compose.yml         # dot-path; arrays are [0], [-1], []
yq '.services.web.ports[]' compose.yml        # [] iterates a sequence

# 2. SET IN PLACE — the whole point
yq -i '.services.web.image = "nginx:1.27"' compose.yml    # -i edits the file
yq -i '.spec.replicas = 3' deploy.yml         # bare number → YAML int
yq -i '.spec.replicas = "3"' deploy.yml       # quoted → YAML string. THE type
                                              # gotcha: "3" and 3 are different
                                              # YAML and the app may care.

# 3. ADD / APPEND / DELETE
yq -i '.services.web.environment += ["DEBUG=1"]' compose.yml   # append to a list
yq -i '.metadata.labels.team = "core"' deploy.yml             # add a new key
yq -i 'del(.services.old)' compose.yml                        # remove a subtree

# 4. INJECT a shell value (don't string-concat it in)
yq -i '.image = strenv(IMG)' deploy.yml       # strenv() = as a string
yq -i '.replicas = env(N)' deploy.yml         # env()    = typed (int stays int)

# 5. BRIDGE to jq when you need jq's muscle
yq -o=json compose.yml | jq '.services | keys'    # YAML → JSON, then jq
yq -p=json -o=yaml data.json                      # JSON → YAML (round the other way)
```

## Why yq and not "convert to JSON, jq, convert back"

```bash
# yq edits the YAML DIRECTLY and keeps comments + key order + formatting. Piping
# through jq and back flattens all of that. Use the jq bridge (step 5) only for
# READING/querying; for EDITING a config you keep, stay in yq -i.
```

## Gotchas

```bash
# - mikefarah ≠ jq: assignment is `=`, update-with-function is `|=`, and helpers
#   like `to_entries`/`keys` exist but the surrounding syntax differs. Don't paste
#   a jq expression and expect it to run.
# - -i writes the file with NO backup. Preview by running the same expr WITHOUT
#   -i first (it prints the whole doc with your change) before committing to disk.
# - Multi-document YAML (--- separators): target one with
#   `yq -i '(select(di == 0) | .foo) = "x"' file` — di = document index.
# - `.a.b = "x"` CREATES the path if missing — a typo in the key silently adds a
#   new key instead of erroring. Read (step 1) to confirm the path exists first.
```
