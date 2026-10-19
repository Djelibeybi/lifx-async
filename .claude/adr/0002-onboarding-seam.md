---
status: accepted (implemented in #336)
---

# lifx-async owns the onboarding protocol and sequence, and host WiFi lives out of tree

`lifx.onboard` owns everything about SoftAP onboarding that is not host WiFi
management: packet 305, the TLS client for the SoftAP, the serial and SoftAP-name
helpers, the seven-phase state machine with its events, results, retry policy and
host recovery, bulk mode, and LAN verification through the `DeviceWatcher`. Scanning
for networks and joining or leaving them are done by code the caller supplies behind
two `typing.Protocol`s, `Scanner` and `Joiner`, plus three optional capabilities
(`CurrentNetworkReporter`, `NetworkForgetter`, `Disassociator`) that the state machine
discovers with `isinstance`. The SoftAP control channel is a third protocol,
`SoftApClient`, with the TLS client as its default. lifx-async ships no implementation
of `Scanner` or `Joiner` and no command line tool; those live in a separate project
that depends on lifx-async and not the other way round.

We chose this because host WiFi management differs on every operating system and
needs subprocesses (`networksetup`, `nmcli`), `ctypes` (`wlanapi.dll`), `pyobjc`
(CoreWLAN) or an app bundle (macOS Location Services). None of that belongs in a
library with no runtime dependencies that is imported by Home Assistant and LedFx,
and none of it is needed to test the part that is hard to get right: the handoff
sequence is full of rules learned on hardware (TCP reachability means joined, retry
the join as well as the scan, forget the SoftAP before rejoining, run host recovery
after cancellation, ignore a sighting at the SoftAP address), and those rules are
the same whatever the backend. Keeping them in one place, driven by a fake `Scanner`
and `Joiner`, means every backend gets them for free and the suite proves them
without a radio. A caller that already knows the full SoftAP name never scans, which
is the only path that works on macOS without Location Services and so is usable with
lifx-async alone.

## Considered Options

- **In-tree backends behind optional extras.** Rejected: an extra still ships
  platform-specific subprocess, `ctypes` and `pyobjc` code under the library's
  release, test matrix and security surface, and `pyobjc` cannot make a macOS
  process Location-Services-aware without an app bundle at all.
- **Subprocess-only backends in tree.** Rejected: it covers macOS `networksetup` and
  Linux `nmcli` but not Windows or the macOS scan, still adds code that shells out
  with the home password in reach, and invites the first backend that puts the
  password on a command line.
- **A private hook instead of a public `SoftApClient` protocol.** Rejected: the
  control channel is the one seam a test must replace, and a public protocol keeps
  that honest and lets a different onboarding channel (BLE or serial) supply its
  own control channel without touching the state machine.

## Consequences

- The sibling project's contract is exactly the protocols and capabilities above,
  `SoftApNetwork.from_ssid()` for building networks (it derives the serial through
  `Serial.from_softap_ssid()`, so the derivation lives in one place), and
  `onboard()` or `bulk_onboard()` for driving them. Anything beyond that is a
  change to lifx-async.
- The password appears only as a `HomeNetwork` field. It never reaches a log, an
  event, an exception message or a `repr`, and library errors repeat only the type
  name of a backend's exception, because a backend that shells out may echo it.
- The SoftAP TLS channel runs with certificate verification off, since devices
  present self-signed certificates with no trust anchor, so the guide documents the
  look-alike SoftAP risk and its mitigations rather than offering a verifier hook.
- The timing defaults are unchanged from the tool they were tuned in, and examples
  never override them.
- Tests ship fakes for the three protocols. Whether each product generation still
  exposes a SoftAP, and which firmware needs `legacy_tls`, is answered on hardware
  separately and does not change this seam.
