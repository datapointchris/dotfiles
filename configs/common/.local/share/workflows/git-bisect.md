# git bisect — binary search for the commit that introduced a bug

```bash
# Manual bisect
git bisect start
git bisect bad                    # current commit is broken
git bisect good v1.0              # this tag/commit was working
```

Git checks out a middle commit. Test it, then tell git:

```bash
git bisect bad                    # if broken
git bisect good                   # if working
git bisect skip                   # if can't test this commit
```

Repeat until git identifies the first bad commit, then reset:

```bash
git bisect reset
```

**Automated bisect** — provide a test command (exit 0 = good, exit 1 = bad):

```bash
git bisect start HEAD v1.0
git bisect run make test
git bisect run ./test-script.sh
git bisect run sh -c 'go build ./... 2>&1 | grep -q "error" && exit 1 || exit 0'
```

```bash
# Replay a previous bisect session
git bisect log                    # show decisions made so far
git bisect replay bisect.log      # replay a saved session
```
