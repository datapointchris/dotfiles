---
icon: material/chart-timeline-variant
---

# Patterns

Quick timestamped note logging for tracking patterns in health, mood, habits, and daily observations. Stores entries in JSONL format for easy analysis.

## Quick Start

```bash
patterns 'had coffee around 3pm'
patterns 'feeling slight heartburn'
patterns 'slept well, 8 hours'
```

Each entry is timestamped and appended to `~/.local/share/patterns/entries.jsonl`.

## Usage

Log a brief observation:

```bash
patterns 'your note here'
```

The command silently appends a JSON entry with timestamp and message.

## Data Format

Entries are stored as JSON Lines (JSONL) in `~/.local/share/patterns/entries.jsonl`:

```json
{"timestamp": "2025-12-11T15:30:45-0500", "message": "had coffee around 3pm"}
{"timestamp": "2025-12-11T18:22:10-0500", "message": "feeling slight heartburn"}
```

Each line is a complete JSON object with:

- `timestamp` - ISO 8601 format with local timezone offset
- `message` - Your note text

## Analysis Examples

View all entries:

```bash
cat ~/.local/share/patterns/entries.jsonl | jq '.'
```

Extract just messages:

```bash
jq -r '.message' ~/.local/share/patterns/entries.jsonl
```

Filter by date:

```bash
jq 'select(.timestamp | startswith("2025-12-11"))' ~/.local/share/patterns/entries.jsonl
```

Format for reading:

```bash
jq -r '"\(.timestamp) | \(.message)"' ~/.local/share/patterns/entries.jsonl
```

Group by date:

```bash
jq -r '.timestamp[:10] + " | " + .message' ~/.local/share/patterns/entries.jsonl | sort
```

## Use Cases

Track patterns over time by logging brief observations:

- **Health tracking** - Food intake, symptoms, energy levels, sleep quality
- **Mood monitoring** - Emotional states, triggers, stress levels
- **Habit formation** - Activities, exercise, meditation, reading
- **Work patterns** - Productivity, focus times, distractions
- **Correlations** - Find connections between activities and outcomes

The goal is to capture many small data points throughout the day for later pattern analysis.

## Data Location

- **Data file**: `~/.local/share/patterns/entries.jsonl`
- **Format**: JSON Lines (one JSON object per line)
- **Backup**: Not tracked in dotfiles (personal data)

Consider backing up this file periodically if you accumulate valuable data.

## Integration

The JSONL format makes it easy to:

- Import into Python/R for statistical analysis
- Process with command-line tools (`jq`, `grep`, `awk`)
- Visualize with plotting libraries
- Query with SQLite or DuckDB

Example Python analysis:

```python
import json
from datetime import datetime

entries = []
with open('~/.local/share/patterns/entries.jsonl') as f:
    for line in f:
        entries.append(json.loads(line))

# Find all entries with 'coffee'
coffee_entries = [e for e in entries if 'coffee' in e['message'].lower()]

# Group by date
from collections import defaultdict
by_date = defaultdict(list)
for entry in entries:
    date = entry['timestamp'][:10]
    by_date[date].append(entry['message'])
```
