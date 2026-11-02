# Security severity rubric

Rate every finding at one of five levels. The levels are the qualitative bands of CVSS v4.0,
published by FIRST, which keeps them identical to CVSS v3.x. A CVSS vector is optional. Where you
give one, its score must fall in the band of the level you chose.

| Level | CVSS v4.0 band | In an intake review of software for a managed machine |
| --- | --- | --- |
| critical | 9.0–10.0 | A third party can run code on the machine with no action by the employee, or a secret in the repository grants access to a real system. |
| high | 7.0–8.9 | Code from a third party runs as root or at every shell start with no integrity check. A security control is disabled or weakened. A root certificate is installed. Sudo is granted without a password. |
| medium | 4.0–6.9 | Code is fetched over HTTPS from a reputable publisher, but its version floats or its checksum is not verified. Persistence such as a timer or service fetches from the network. A credential is written where another user or a log can read it. |
| low | 0.1–3.9 | Hygiene with a plausible but unlikely path to harm, such as an unpinned tool that runs only by hand, or a world-readable file holding nothing secret. |
| informational | 0.0 | An observation the reviewer records with no risk attached, including a control the repository does well. |

When two levels fit, weigh likelihood against impact as the OWASP Risk Rating Methodology does.
Likelihood is how easily and how often the path is reached. Impact is what an attacker gains on this
machine and from it. A path reached at every shell start is more likely than one reached only by an
install run once.

## Classify every finding

- **Name one CWE** from MITRE's list, such as CWE-494 (Download of Code Without Integrity Check),
  CWE-829 (Inclusion of Functionality from Untrusted Control Sphere), CWE-798 (Use of Hard-coded
  Credentials), CWE-276 (Incorrect Default Permissions), CWE-426 (Untrusted Search Path) or CWE-250
  (Execution with Unnecessary Privileges).
- **Name the MITRE ATT&CK techniques** the behavior matches, where it matches one. An EDR detects by
  these, so they predict what the company's controls will alert on. Common ones for dotfiles are
  T1546.004 (Unix Shell Configuration Modification), T1053.003 (Cron), T1543.002 (Systemd Service),
  T1543.001 (Launch Agent), T1574.007 (Path Interception by PATH Environment Variable), T1553.004
  (Install Root Certificate), T1562.001 (Disable or Modify Tools), T1105 (Ingress Tool Transfer),
  T1552.001 (Credentials In Files) and T1098.004 (SSH Authorized Keys).

## What the large programs check

These are the checks the industry's supply-chain programs run. Use them as the list of questions for
the inventory, never as findings on their own.

- **OpenSSF Scorecard**: Pinned-Dependencies, Signed-Releases, Binary-Artifacts, Dangerous-Workflow,
  Token-Permissions, Maintained, Vulnerabilities and Security-Policy.
- **SLSA**: whether each artifact has provenance tying it to the source and build that made it.
- **NIST SSDF (SP 800-218)**: whether third-party components are verified before use, and whether
  the project protects its own code and release process.
- **CIS Benchmarks** for the operating system: whether a change weakens the hardened baseline.

## Remediation

Give a remediation for every finding where one exists, and name its kind. A code change is a change
to the repository. A configuration is a setting the employee chooses at install. A compensating
control is something the company does instead, such as allowlisting a binary. Accept-risk means the
reviewer would sign off unchanged. None-available means no fix is known.

## Verdict

- **reject** when any finding is critical, or a high finding has no remediation.
- **approve-with-conditions** when any finding is high or medium and each has a remediation. Each
  condition names the finding it clears.
- **approve** when every finding is low or informational.
