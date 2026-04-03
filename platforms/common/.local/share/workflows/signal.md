# Signal — Content Analysis

Analyze a URL, connect it to your life, or batch-process a playlist.

## Single item

```bash
signal analyze <url>                  # summarize, save to DB, display
signal analyze <url> --discuss        # summarize then open Claude session
signal analyze <url> --relate         # summarize then open session with ~/obsession/ context
signal analyze <url> --producer       # also pull in ~/producer/ context
signal analyze <url> --force          # re-run even if already in DB
```

## Batch from playlist or file

Small batches (≤10) get full cross-analysis. Large batches get topic-clustered into pending groups.

```bash
signal batch "https://youtube.com/playlist?list=PLxxx" --name "label"
signal batch ~/links.txt --name "label"   # one URL per line, # = comment
signal batch <source> --relate            # open relate session after meta-analysis
```

When a batch is too large, signal saves clusters and tells you what to run next:

```bash
signal status                  # see pending clusters
signal resume <id> --relate    # run focused meta-analysis on a cluster
```

## Finding past analyses

```bash
signal show                    # fzf picker across all saved analyses
signal search "stoicism"       # full-text search → returns content IDs
signal show <id> --content     # display a content item from search results
signal show <id> --relate      # display analysis then open relate session
```

## Common patterns

Watch a playlist, understand the themes before diving in:

```bash
signal batch "https://youtube.com/playlist?list=PLxxx" --name "topic" --relate
```

Encountered something interesting, want to think about it deeply:

```bash
signal analyze <url> --relate
```

Build a reading list from a playlist, filter it, then analyze:

```bash
# save playlist URLs to a file, remove ones you don't want
signal batch ~/links.txt --name "filtered"
```

Already analyzed something and want to revisit it with fresh context:

```bash
signal show                    # pick from fzf
signal show <id> --relate
```
