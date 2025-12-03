# Run Shell Command with Logging

`mkdocs serve --verbose > /tmp/mkdocs.log 2>&1 &`

This will:

- Run mkdocs serve with verbose output
- Redirect both stdout and stderr to /tmp/mkdocs.log
- Run it in the background with &

Then you can:

- View the log: cat /tmp/mkdocs.log
- Watch it live: tail -f /tmp/mkdocs.log
- Search for specific things: grep "Watching" /tmp/mkdocs.log

When you're done, kill the server:
`pkill -f "mkdocs serve"`

Or if you want to see the output in real-time while also saving to a file, use tee:

`mkdocs serve --verbose 2>&1 | tee /tmp/mkdocs.log`

This way you see the output in your terminal AND it gets saved to the log file.
