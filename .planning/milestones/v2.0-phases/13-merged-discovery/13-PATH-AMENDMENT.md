# Phase 13 Path Amendment

Plan 13-07 consolidates discovery under one canonical package hierarchy. Path
references in Plans 13-01 through 13-06, their summaries, `13-RESEARCH.md`,
`13-PATTERNS.md`, and `13-REVIEWS.md` remain immutable descriptions of the
checkout in which that work was performed. Read those historical references
through this current mapping:

| Historical path | Current disposition |
| --- | --- |
| `src/lifx/network/discovery.py` | Public compatibility umbrella at `src/lifx/network/discovery/__init__.py`; canonical UDP implementation at `src/lifx/network/discovery/udp.py` |
| `src/lifx/network/discovery_coordinator.py` | `src/lifx/network/discovery/coordinator.py` |
| `src/lifx/network/mdns/` | Canonical implementation at `src/lifx/network/discovery/mdns/`; former package contains only supported compatibility re-exports |
| `src/lifx/network/discovery_observation.py` | Removed from the installed package; repository-only models, value-suppressed representation, context and capture live at `tests/test_discovery_observation.py` |

Production retains only inert private callable plumbing for a repository
measurement observer. It imports neither `tests` nor any observation model or
context state. The documented imports `lifx.network.discovery.DiscoveredDevice`,
`lifx.network.discovery.DiscoveryResponse`, and
`lifx.network.discovery.discover_devices` remain compatible, as does the
supported `lifx.network.mdns` public surface through thin aliases.
