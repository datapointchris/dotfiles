# shell redirects and logging

```bash
# Redirect stdout to file
command > output.log              # overwrite
command >> output.log             # append

# Redirect stderr to file
command 2> errors.log

# Redirect both stdout and stderr
command > output.log 2>&1         # both to same file
command &> output.log             # shorthand (bash/zsh)

# Run in background with logging
command > /tmp/app.log 2>&1 &

# Then monitor
tail -f /tmp/app.log              # watch live
grep "ERROR" /tmp/app.log         # search for errors
cat /tmp/app.log                  # read full log

# See output AND save to file (tee)
command 2>&1 | tee output.log           # stdout + file
command 2>&1 | tee -a output.log        # append mode

# Discard output
command > /dev/null 2>&1          # silence everything
command 2>/dev/null               # silence only errors

# Pipe stderr separately
command 2>&1 1>/dev/null | grep "ERROR"  # only stderr through pipe

# Kill a backgrounded process
pkill -f "command"
jobs                              # list background jobs
kill %1                           # kill job 1
```
