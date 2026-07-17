---
tags: [sops, age, secrets, encryption, yaml, homelab, recipe]
---

# edit encrypted secrets (sops + age: decrypt-in-editor, re-encrypt on save)

```bash
# GOAL: read or change a secret in a sops-encrypted file (e.g. homelab's
# pyinfra/group_data/secrets.yaml) and commit the ENCRYPTED result. Backend here
# is age — your private key lives at ~/.config/sops/age/keys.txt (the default
# SOPS_AGE_KEY_FILE), and the matching public recipient is declared per-path in
# the repo's .sops.yaml. sops encrypts VALUES, not keys, so structure stays
# readable and diffs are reviewable.

# 1. EDIT — the daily action
sops secrets.yaml            # decrypts into $EDITOR, re-encrypts + re-MACs on
                             # save. NEVER hand-edit the encrypted file — that
                             # breaks the MAC and sops refuses to decrypt it.

# 2. READ one value without opening the editor
sops -d secrets.yaml | yq '.database.password'   # -d = decrypt to stdout,
                                                 # then bridge to yq (see
                                                 # patch-a-yaml-config).

# 3. NEW secret file — let .sops.yaml pick the recipient
#    Create it at a path the repo's .sops.yaml creation_rules match, then:
sops -e -i newsecrets.yaml   # -e encrypt, -i in place. The path_regex in
                             # .sops.yaml selects the age recipient — no key on
                             # the command line.

# 4. USE secrets without writing plaintext to disk
sops exec-env secrets.yaml 'deploy.sh'   # runs the command with each secret
                                         # injected as an env var; nothing
                                         # decrypted ever hits the filesystem.

# 5. AFTER changing recipients in .sops.yaml (added/rotated a key)
sops updatekeys secrets.yaml # re-encrypts the data key for the NEW recipient
                             # set. Editing .sops.yaml alone does NOT re-key
                             # existing files — this step does.
```

## Gotchas

```bash
# - Encryption of a NEW file is driven ENTIRELY by .sops.yaml creation_rules
#   path_regex. homelab's rule only matches `pyinfra/group_data/secrets\.yaml$`
#   — a file elsewhere won't auto-encrypt. Check the regex before creating.
# - Commit the ENCRYPTED file. The age PRIVATE key (~/.config/sops/age/keys.txt)
#   never goes in git — that's the whole point.
# - "no matching creation rules" on encrypt → the path doesn't match any regex.
#   "no key could decrypt" on edit → this machine's age key isn't a recipient.
# - sops encrypts values only; a secret's KEY NAME and the YAML shape are
#   cleartext. Don't put anything sensitive in a key name.
```
