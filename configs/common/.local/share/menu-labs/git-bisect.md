---
tags: [git, bisect, debug, version-control]
cadence: 2mo
---

# Find the commit that broke it with git bisect

> `git bisect` binary-searches history for the commit that introduced a bug —
> log2(n) checkouts instead of reading every diff. This Lab drills a full bisect
> on a scratch repo where exactly one commit breaks a test.

## Setup

Builds 15 commits; commit 8 flips `answer` from 42 to 41 (the "bug"):

```bash
LAB=$(mktemp -d) && cd "$LAB"
git init -q
for n in $(seq 1 15); do
  val=42; [ "$n" -ge 8 ] && val=41
  # rev=$n makes every commit a real change; answer flips at commit 8
  printf "answer=%s\nrev=%s\n" "$val" "$n" > value.txt
  git add value.txt && git commit -qm "commit $n"
done
cat > test.sh <<'EOF'
#!/usr/bin/env bash
grep -q 'answer=42' value.txt   # passes only when answer is 42
EOF
chmod +x test.sh
```

## Steps

1. **Start and mark the boundaries.** `git bisect start` → `git bisect bad` (HEAD
   is broken) → `git bisect good HEAD~14` (the first commit was fine).
   - Expect: git checks out a commit in the middle and reports the steps
     remaining.
   - Why: bisect needs one known-bad and one known-good end to search between.

2. **Test, then mark, repeatedly.** At each checkout run `./test.sh; echo $?`,
   then `git bisect good` (exit 0) or `git bisect bad` (exit 1).
   - Expect: after ~4 rounds git prints `<hash> is the first bad commit`.
   - Why: each answer halves the range — you test only log2(15) ≈ 4 commits.

3. **Read the culprit.** `git show` the reported hash.
   - Expect: the diff flipping `answer=42` to `answer=41` — commit 8.
   - Why: bisect lands exactly on the transition.

4. **End the session.** `git bisect reset`
   - Expect: HEAD returns to the tip you started from.
   - Why: `git bisect reset` closes the bisect and restores your original
     checkout.

## Automate it

`git bisect run` marks each step for you from a script's exit code:

```bash
git bisect start HEAD HEAD~14      # bad (HEAD), then good, in one line
git bisect run ./test.sh           # git drives straight to the first bad commit
git bisect reset
```
