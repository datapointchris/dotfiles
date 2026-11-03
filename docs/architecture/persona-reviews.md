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

A subject's `exclude` list removes paths from every export of it, as `git archive` exclude
pathspecs. The dotfiles subject carries the review tool itself, whose catalog of personas, rubrics
and prompts would otherwise be read as evidence by the session those same files instruct. The
excluded paths are stamped on the run's record and named to the reviewer, who lists them in
`limitations`.

## The session sees the subject as evidence and nothing of this machine

The session starts in a fixed empty directory and reaches the subject through `--add-dir`. The
subject ships its own `CLAUDE.md` and README, and a session started inside it would load them as
instructions. The system prompt names every file in the subject as evidence, and treats text
steering the review as a finding. `--setting-sources ''` and `--safe-mode` keep this machine's
settings, memory, hooks and MCP servers out, so the same scenario reviews the same way on any
box. `headless_call.py` holds the argv.

The persona's `tools` list says what exists. The security persona reads with Read, Glob and Grep,
and reaches upstream projects with WebSearch and WebFetch. It gets no Bash and no Write.

Only the web tools are pre-approved. Claude Code answers Read, Glob and Grep on its own inside the
start directory and the `--add-dir`, and `--permission-prompts none` refuses them everywhere else.
Pre-approving Read lifts that limit: a session given `--allowed-tools Read` read a file outside the
export. A session that reads anywhere and fetches any URL could send a local file out if a subject
steered it, and steering is what the persona is there to catch.

## Effort is stated on every call, because the machine's setting never reaches the session

`--setting-sources ''` drops a machine's `effortLevel`, so a call with no `--effort` takes whatever
Claude Code's default is in that release. A review would then change with an upgrade, and nothing
would say so, because no frame echoes the effort. A persona names its `effort`, `run --effort`
overrides it for one run, and the record stamps the value the call was given. Medium is the default,
because it is Anthropic's starting point for agent work on Opus. A second run at a higher effort on
the same commit measures what the extra effort buys.

## The reviewer knows its request cap, because its report comes last

The report arrives only in the session's final reply. A session that reaches `--max-turns` delivers
nothing but its token counts, however much it had read. So the system prompt names the cap, tells the
reviewer to group its tool calls, and asks for the report by four fifths of the cap. Whatever it did
not reach goes in `limitations`, which is worth more than no report.

## The report schema refuses a stub, because the first accepted report ends the session

The first report the schema accepts ends the session, and the model cannot tell that from the tool.
A haiku run had a real report refused three times, then sent a stub to isolate the fault: a `summary`
reading `Test`, one inventory item, no findings. That stub was accepted and stored as the session's
success. The prompt now says the first accepted report is final, and the record counts
`rejected_reports`, but a prompt only asks.

So the schema is the admission gate. `summary` and each `limitations` and `conditions` item carry a
minimum length, set well below what real reports send. The verdict requires what the rubric ties to
it: `approve-with-conditions` needs a finding and a condition, `reject` needs a finding, and conditions
exist only under `approve-with-conditions`. A session that never clears the gate ends
`no-structured-reply`, a failure the record shows rather than a stub stored as a success. The API
accepts `if`, `then` and `else` at the top of a tool's schema. Each conditional keyword sits beside a
`type`, because Ajv's strict mode otherwise warns on stderr.

## `summary` is sent last, so a slip in it has nothing to swallow

The model sends a report as tool parameters, writing each array as JSON and each string as bare text.
Now and then it closes a long string with the parameter's own name, `</summary>`, where `</parameter>`
belongs. The next parameter then lands inside the string, and the schema answers `must have required
property 'inventory'`. This hit two or three of ten real-condition haiku reports, and each cost a full
resend. Across stored transcripts every such slip was on a string parameter, on Haiku and on Opus.

Schema order alone does not move the field. With `summary` last in `properties` and `required`, 5 of 6
haiku reports still sent it second. Its description saying to send it last moved 6 of 6. What a slip in
the last position does has not been observed, since no parameter follows it to lose.

*Rejected:* `summary` as an array of sentences, which removes the long string altogether. 6 of 12 haiku
reports wrote the array as bare prose, which the tool refuses as `could not be parsed as JSON`.

## A run streams its frames, so a person can watch it and a dead run keeps its work

`--output-format json` prints one array when the session ends. A long review would sit silent for
as long as it ran, and a timeout, a kill or a Ctrl-C would leave nothing: no frames, and a record
reading zero tokens. So a run reads `stream-json` a line at a time. Each frame goes to `frames.jsonl`
as it arrives, and each step prints to stderr with the request count and the context size, which
leaves stdout for the record.

An assistant frame's `usage` carries only the output counted so far, so a run with no result frame
reads its tokens from the session's transcript, and the record's `tokens_from` says so. Ctrl-C ends
the session and still stores the record, under the key `interrupted`, and exits 130.

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
