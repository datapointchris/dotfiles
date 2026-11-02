# Persona Reviews

`persona-review` puts a model in front of a subject as a named reviewer would sit there. A
security engineer deciding whether software may go on a managed laptop is the first. The review
is one point in a test matrix with four axes: the persona, the machine, the operating system and
the subject. Each axis is a directory of YAML under `src/dotfiles/persona_review/`, one file per
value. A scenario picks one value on each and adds the submitter's own words. `persona-review
matrix` lists every point the machines allow.

The pattern is a CI build matrix, such as GitHub Actions' `strategy.matrix` or tox's factor
lists, with an LLM-as-judge in the job's place. A machine's `operating_systems` plays the part of
the matrix's `exclude`: a 2018 Mac mini never runs WSL, so that point does not exist.

## The reviewer axis is a persona, because profile already means a package bundle

`install/profiles/` holds the package bundles a manifest takes, and the CLI says "profile" for
them. Calling the reviewer a profile as well would give one word two meanings in the same repo.
The axis is the persona, and the persona file names the rubric and the report schema it replies
in.

## The subject is exported at a commit, never read in place

A run extracts the subject with `git archive` into the run's own directory. The review then reads
exactly the commit that was submitted, and its record names that commit, so a finding can be
checked against the same tree later. Reading the checkout in place would review uncommitted
edits and whichever branch happened to be out. The export also drops the subject's `.git`, so a
reviewer cannot be steered by history the submitter never sent.

`--only PATH` narrows the export. A narrow export is the cheap run that checks a prompt or schema
change, and the persona says what it could not review in the report's `limitations`.

## The session sees the subject as evidence and nothing of this machine

The session starts in a fixed empty directory and reaches the subject through `--add-dir`. The
subject ships its own `CLAUDE.md` and README, and a session started inside it would load them as
instructions. The system prompt names every file in the subject as evidence, and treats text
steering the review as a finding. `--setting-sources ''` and `--safe-mode` keep this machine's
settings, memory, hooks and MCP servers out, so the same scenario reviews the same way on any
box. `headless_call.py` holds the argv.

The persona's `tools` list is the confinement. The security persona reads with Read, Glob and
Grep, and reaches upstream projects with WebSearch and WebFetch. It gets no Bash and no Write.

## Severity is CVSS v4.0's five bands, classified by CWE and ATT&CK

The rubric uses the qualitative bands FIRST publishes for CVSS v4.0: critical, high, medium, low,
and informational for a score of zero. NVD reports in the same bands. A CVSS vector is optional.
CVSS scores a vulnerability in a product, and many intake findings, such as an unpinned download,
are a missing control rather than a vulnerability. Every finding names a CWE, and
names the MITRE ATT&CK technique its behavior matches. An EDR detects by technique, so the
technique predicts what the company's controls would alert on. Linking a shell startup file is
T1546.004 whether or not anything malicious is in it.

*Rejected:* SARIF as the report format. SARIF describes a static analyzer's results against
rules, and has no place for a verdict, an inventory of what the install brings, or conditions of
approval. The report schema keeps SARIF's essentials, a rule id and a located result, as `cwe`
and `locations`.

## A mock run exercises everything except the call

`run --mock` exports the subject, renders both prompts, writes argv and stores the record, then
writes the persona's canned report from `mock-reports/` instead of calling a model. A change to
the catalog, the prompts or the storage is checked for no tokens. The first real call on a
changed schema goes to the smallest model with a narrow `--only` and a low `--max-turns`.

The schemas declare draft-07. Claude Code checks `--json-schema` with Ajv's default class, which
holds only the draft-07 meta-schema, and refuses a schema naming draft 2020-12 before any model
call. A schema in the dialect its validator enforces passes through unchanged.
