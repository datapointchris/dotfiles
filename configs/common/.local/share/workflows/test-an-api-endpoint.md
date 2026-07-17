---
tags: [curl, jq, api, http, rest, debug, recipe]
---

# test an API endpoint from the terminal (curl → jq: probe → auth → POST → debug)

```bash
# GOAL: hit an HTTP endpoint, see what it actually returns, and iterate — the
# terminal loop for building against or debugging a REST API. curl fetches, jq
# parses; the two are almost always used together.

# 1. PROBE — is it up, what status, what headers?
curl -i https://api.example.com/health     # -i INCLUDES the response headers +
                                           # status line. First thing to run —
                                           # tells you 200 vs 401 vs 500 before
                                           # you worry about the body.

# 2. GET + PARSE — clean body into jq
curl -s https://api.example.com/users | jq '.[] | .name'
#    -s = SILENT: drop curl's progress meter, which otherwise corrupts jq's stdin.
#    Rule: the moment you pipe curl anywhere, add -s.

# 3. AUTH — bearer token / basic
curl -s -H "Authorization: Bearer $TOKEN" https://api.example.com/me | jq
curl -s -u user:pass https://api.example.com/private | jq      # -u = basic auth

# 4. POST JSON — send a body
curl -s -X POST https://api.example.com/users \
     -H "Content-Type: application/json" \
     -d '{"name":"ada","role":"admin"}' | jq
curl -s -X POST ... -d @payload.json | jq   # -d @file reads the body from a file

# 5. DEBUG — when it misbehaves
curl -v https://api.example.com/thing       # -v = verbose: the full request,
                                            # redirects, TLS handshake, both header
                                            # sets. This is how you see WHY.
curl -sL https://api.example.com/thing      # -L follows redirects (APIs love 301→)

# 6. TIMING / STATUS ONLY — no body
curl -s -o /dev/null -w '%{http_code}  %{time_total}s\n' https://api.example.com/x
#    -o /dev/null throws the body away; -w prints just the fields you asked for.
```

## Gotchas

```bash
# - `-d` IMPLIES -X POST and sets Content-Type: application/x-www-form-urlencoded.
#   For a JSON API you MUST add `-H "Content-Type: application/json"` or the
#   server rejects the body. (-X POST alone is redundant once -d is present.)
# - Want -d values as a GET query string instead of a POST body? add -G.
# - Single-quote JSON bodies so the shell doesn't eat the double quotes; or use
#   -d @file.json to sidestep quoting entirely.
# - No -s → the progress meter goes to stderr but the moment you redirect or the
#   terminal is narrow it bites you; make -s reflexive when piping to jq.
```
