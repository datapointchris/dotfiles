"""What a provider is allowed to know about the run it is installing into.

`registry.py` is handed the run and reads eight things off it: `offline`, `home`,
`machine`, `reinstall`, `plan`, `inventories`, `force` and `catalog`. Naming those
eight as a structural type is what lets the providers stay below `session` in the
layer order, because `Session.plan` calls `resolve()` and `resolve()` walks
`registry.PROVIDERS` — a three-edge cycle no ordering of layers can express.

**Every member is a read-only `property`.** `Session` is a frozen dataclass, so a
plain `offline: bool` here declares a settable variable and nothing frozen can
satisfy it. The failure is *"Protocol member MachineContext.force expected
settable variable, got read-only attribute"*, raised at the call sites that pass a
Session rather than here.

**The four types are imported under `TYPE_CHECKING`.** This module is a
declaration and has no runtime behaviour, so importing four modules to describe
one would make a leaf into a hub. `Inventories` is the one that matters:
`evidence` imports `resources`, and a runtime edge from here would put this module
inside that graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from dotfiles.catalog import Catalog
    from dotfiles.evidence import Inventories
    from dotfiles.machine import Machine
    from dotfiles.plan import Plan


class MachineContext(Protocol):
    """The run, as much of it as a provider may see.

    Narrower than a `Session` on purpose: a provider that wants a ninth thing has
    to declare it here, where the widening is visible, rather than reaching for
    whatever a Session happens to carry.
    """

    @property
    def home(self) -> Path:
        """The home directory this run converges, which tests point elsewhere."""
        ...

    @property
    def offline(self) -> bool:
        """Whether this run may spend the network at all."""
        ...

    @property
    def force(self) -> bool:
        """Authorisation to destroy what this repo did not create."""
        ...

    @property
    def reinstall(self) -> bool:
        """Install again whatever measuring concludes, for everything this run covers."""
        ...

    @property
    def catalog(self) -> Catalog:
        """Everything `packages.yml` declares, parsed once per run."""
        ...

    @property
    def machine(self) -> Machine:
        """The manifest naming what this box is and what it subscribes to."""
        ...

    @property
    def plan(self) -> Plan:
        """The whole run's resolved plan, which is wider than the slice a provider is handed."""
        ...

    @property
    def inventories(self) -> Inventories:
        """What the package managers report, measured once and shared."""
        ...
