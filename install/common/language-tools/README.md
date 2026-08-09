# Language Tool Installers

Installers for tools distributed through a language's own package manager, driven by the tool lists
in `packages.yml`. Two remain — npm globals and uv tools — and both are being replaced by providers
under `src/dotfiles/providers/`, which is where the go and cargo installers went. The scripts here
are what is left of the pattern, not a place to add to.

## The pattern

Each script reads its section of `packages.yml` through `parse_packages`, loops, installs, and
reports a failure per package via `output_failure_data` rather than stopping. Continuing is the
point: one unreachable registry must not cost the machine the other twenty tools.

```bash
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

dotfiles_python -m dotfiles.parse_packages --type=npm | while read -r package; do
  npm install -g "$package" \
    || output_failure_data "$package" "https://www.npmjs.com/package/$package" "latest" \
      "npm install -g $package" "Failed to install via npm"
done
```

The runtime each installs against is already present: `registry.ToolchainProvider` converges uv,
rustup, Go and fnm's default Node at an earlier stage, derived from these tool lists rather than
from a manifest boolean.

## Why the others are gone

A script has two modes — install and update — and the mode decided things it had no business
deciding: which source a tool came from, and whether a present-but-old tool was left alone. A
provider has one verb and asks the question the modes were approximating, which is whether this run
has a network. It also gets currency for free: `go install @latest` and `cargo binstall` *are* the
upgrade, so being behind the upstream a declaration names is drift `plan` reports and `apply`
repairs, rather than something only `update.sh` could see.

See `docs/architecture/package-management.md` for where each section installs from, and
`packages.yml`'s header comment for which section a new tool belongs in.
