# Onboarding

A factory-fresh or reset LIFX device is not on your network. It runs its own
open WiFi network, a *SoftAP*, whose name starts with `LIFX` and ends with six
hex characters of the device's identity, for example `LIFX Candle Color 8274eb`.
It waits for a host to join that network, open a TLS connection to
`172.16.0.1:56700` and hand it the credentials of the network it should use.

`lifx.onboard` does everything in that exchange except the host's own WiFi
management: it parses the SoftAP name, speaks to the device, walks the
sequence of phases, returns the host to its own network and confirms the
device appeared on the LAN. Import it explicitly. Nothing in it is exported
from the top-level `lifx` namespace, and it adds no dependencies.

```python
from lifx.onboard import HomeNetwork, onboard
```

Joining and leaving WiFi networks differs on every operating system and needs
subprocesses, `ctypes` or an app bundle, so lifx-async leaves it to you. You
supply a [`Scanner`](#what-you-supply) and a [`Joiner`](#what-you-supply); the
library supplies the rest. See [What lifx-async does not
ship](#what-lifx-async-does-not-ship).

## The home network and the password

`HomeNetwork` is the network the device should join. It is the only place a
password goes. Read it from the environment, a no-echo prompt or a secret
store; never put it in a literal or on a command line, where it would show in
`ps` and shell history.

```python
import os

from lifx.onboard import HomeNetwork

network = HomeNetwork("Home-Network", os.environ["LIFX_HOME_PASSWORD"])
```

```python
import getpass

network = HomeNetwork("Home-Network", getpass.getpass("Home WiFi password: "))
```

The security mode defaults to open for an empty password and WPA2 otherwise;
pass `security=WifiSecurity.WPA2_AES_PSK` (or another `WifiSecurity` value) to
choose one. An SSID over 32 bytes or a password over 64 bytes (as UTF-8) is
rejected with `ValueError` rather than truncated, because a device handed
silently shortened credentials joins nothing and gives no reason. A secured
mode with no password raises `MissingCredentialsError`, which is also a
`ValueError`.

The password is never logged, never put in an event or an exception message,
and never shown by `repr()` or `str()`. No lifx-async function takes it
anywhere except as a `HomeNetwork` field.

## Onboarding one device

If you already know the device's full SoftAP name, pass it as the target. No
scan happens, so no `Scanner` is needed: this is the path that works on macOS
without Location Services (which redacts scan results) and the one a Home
Assistant integration can use with lifx-async alone.

```python
from lifx.onboard import onboard

result = await onboard(
    network,
    scanner=None,
    joiner=joiner,
    target="LIFX Candle Color 8274eb",
)
print(result.serial, result.verified, result.host_network)
```

`joiner` here is your own [`Joiner`](#what-you-supply). `onboard()` returns a
`Result` on success and raises a [`LifxOnboardError`](#results-and-errors) on
failure.

### Choosing the target

| `target` | What happens | Needs a `Scanner` |
|----------|--------------|-------------------|
| A full SoftAP name such as `LIFX Candle Color 8274eb` | The name is parsed into a serial and the scan phase is skipped | No |
| A serial (`d073d58274eb`, with or without `:`, `-` or spaces) or a `Serial` | The scan waits for the SoftAP carrying that serial | Yes |
| The six-hex suffix (`8274eb`) | The same, with the LIFX prefix `d073d5` added | Yes |
| `None` | The first LIFX SoftAP the scan returns | Yes |

A target that is none of these raises `InvalidSoftApTargetError` before any
phase runs. A serial, suffix or no target with `scanner=None` raises
`ValueError` before any phase runs. A target that starts `LIFX` and parses as a
SoftAP name never scans.

```python
result = await onboard(network, scanner=scanner, joiner=joiner, target="d073d58274eb")
result = await onboard(network, scanner=scanner, joiner=joiner, target="8274eb")
result = await onboard(network, scanner=scanner, joiner=joiner)
```

Prefer a serial or a full name to `None`. With no target the library joins the
first SoftAP it sees, which in a building full of devices in setup mode is not
necessarily yours. See [Security](#security).

## The sequence

`onboard()` runs seven phases, named by `OnboardPhase`. Each emits events, and
each failure is a typed exception that records its phase.

| Phase | What it does | What it waits for |
|-------|--------------|-------------------|
| `SCAN` | Calls `scanner.scan()` repeatedly until a matching SoftAP appears. Skipped for a full SoftAP name. | The SoftAP to appear, up to `FIND_TIMEOUT`, polling every `FIND_POLL` |
| `JOIN` | Calls `joiner.join()` repeatedly. A freshly reset device takes a while to raise its SoftAP, so the join itself is retried, not just the scan. | The join to succeed, with the same budget |
| `WAIT` | Probes `172.16.0.1:56700` with a plain TCP connection. Reachability of that address is what counts as joined, never the SSID the operating system reports. | A probe to connect, up to `WAIT_TIMEOUT`, every `WAIT_POLL` |
| `DIAL` | Opens the TLS connection to the SoftAP. | The handshake, up to `DIAL_TIMEOUT` |
| `CONFIGURE` | Writes one packet 305 (`Wifi.SetAccessPoint`) message carrying the home network, then closes. Nothing is read back. | The write to flush |
| `REJOIN` | Returns the host to its own network (see below). | The host to land on one of the networks it may be returned to, up to `REJOIN_TIMEOUT` for each |
| `VERIFY` | Waits for the device to show up on the LAN through a `DeviceWatcher`. | A sighting, up to `VERIFY_TIMEOUT` |

The values are constants in `lifx.onboard`; see the [API
reference](../api/onboarding.md#timing-defaults). They were tuned on hardware,
so leave them alone unless you have measured a reason not to.

### Returning the host to its network

From the first attempt to join the SoftAP until the host is back on its own
network, any failure or cancellation runs *host recovery*. It starts that early
because a backend can change the association and then keep waiting on DHCP or a
subprocess, so even a cancelled `join()` may have moved the host. It is shielded from the
caller's cancellation, bounded in time, best effort, and logs rather than
raises. A cancelled `onboard()` therefore never leaves the machine stranded on
the device's network; `asyncio.CancelledError` propagates once recovery has
finished.

The `REJOIN` phase does this, in order:

1. Forget the SoftAP from the host's saved networks, if the `Joiner` or
   `Scanner` can (`NetworkForgetter`). Otherwise the operating system waits for
   the SoftAP to come back.
2. Disassociate, only if the host is still on the SoftAP (`Disassociator`).
3. Prefer the operating system's own auto-join. The `AUTO_JOIN_WAIT` budget
   starts only once the host has left the SoftAP. If the host lands on the
   original network, or on some other network it knows, that is accepted and
   reported in `REJOINED` and `Result.host_network`.
4. Otherwise call `joiner.rejoin()` until it works, treating "already on the
   target" as success even when the `Joiner` reported an error.

The targets, best first, are `rejoin_ssid` when you give one (with
`rejoin_password`, which defaults to the home password when `rejoin_ssid` is
the home SSID), then the network the host was on before onboarding, then the
home network you handed the device. When the original network is unknown or is
the home network, only the home network is tried.

## What you supply

lifx-async defines two protocols for the host's WiFi interface and ships no
implementation of either. All their methods are `async`.

- `Scanner.scan(*, min_rssi=0.0, include_non_lifx=False)` returns a list of
  `SoftApNetwork`, only LIFX SoftAPs unless `include_non_lifx` is set. An empty
  list with no error is a valid answer. `Scanner.interface` is a read-only
  string used for diagnostics.
- `Joiner.join(network)` joins a SoftAP and must be idempotent.
  `Joiner.rejoin(ssid, password="")` joins the named network.

Build the networks a scanner returns with `SoftApNetwork.from_ssid()`. It
derives the serial through `Serial.from_softap_ssid()`, so the derivation lives
in one place.

```python
from lifx.onboard import SoftApNetwork


class ExampleScanner:
    """Skeleton: ask the operating system what it can see."""

    interface = "wlan0"

    async def scan(
        self, *, min_rssi: float = 0.0, include_non_lifx: bool = False
    ) -> list[SoftApNetwork]:
        ssids: list[str] = []  # the SSIDs the operating system reports
        return [SoftApNetwork.from_ssid(ssid) for ssid in ssids if ssid.startswith("LIFX")]


class ExampleJoiner:
    """Skeleton: join and leave networks through the operating system."""

    async def join(self, network: SoftApNetwork) -> None: ...

    async def rejoin(self, ssid: str, password: str = "") -> None: ...
```

Three optional capabilities improve recovery. Each is a `runtime_checkable`
protocol that the library tests for with `isinstance`:

| Capability | Method | Used for |
|------------|--------|----------|
| `CurrentNetworkReporter` | `async current_ssid() -> str \| None` | Noticing the host left the SoftAP early, recording the original network, letting auto-join count as a rejoin, and naming the network it landed on in `Result.host_network` |
| `NetworkForgetter` | `async forget(ssid)` | Removing the SoftAP from saved networks before rejoining |
| `Disassociator` | `async disassociate()` | Dropping the SoftAP association before the operating system picks a network |

The contract the library relies on:

- The capabilities are `async` coroutines, like `scan()` and `join()`.
- The `Joiner` is consulted before the `Scanner` for every capability, because
  the `Joiner` owns the association and must win over a scanner that happens to
  implement the same method.
- Library errors carry only the *type name* of a backend's exception, never its
  message and never a chained cause. A backend that shells out may echo its
  arguments, password included, into its error text, so the library never
  repeats or chains it. Put detail you want kept in your own logs.
- A backend failure never leaves the host on the SoftAP: recovery runs after any
  failure from the first join attempt onward. Every backend call is bounded:
  `scan()` and `join()` by what is left of `find_timeout` (a bulk scan by
  `find_timeout` or the remaining idle window), the wait phase's reporter polls
  and probes by `wait_timeout`, `forget()`, `disassociate()`, `rejoin()` and
  other reporter polls by `rejoin_timeout`, with a rejoin target's retries
  sharing one `rejoin_timeout`. A backend that never
  returns therefore fails its phase instead of hanging the run, and cannot
  starve the next rejoin target or the recovery pass of its budget.

## Legacy TLS

The SoftAP's TLS connection uses TLS 1.2 or later by default. Firmware older
than about 2020 speaks only TLS 1.0 with the `AES256-SHA` cipher suite, which
modern OpenSSL refuses. Pass `legacy_tls=True` to pin that configuration:

```python
result = await onboard(
    network,
    scanner=None,
    joiner=joiner,
    target="LIFX Candle Color 8274eb",
    legacy_tls=True,
)
```

If the host's OpenSSL will not allow TLS 1.0 at all, `onboard()` raises
`LegacyTlsUnavailableError` naming the OpenSSL version, so the failure is
attributed to the host and not the device. The option is off by default; the
[hardware verification status](#hardware-verification-status) says which
firmware needs it once that is known.

## Events

Progress reaches you two ways, and neither can slow the sequence down.

`on_event` is a callable invoked synchronously with each `OnboardEvent`. It is
never awaited, and an exception it raises is logged. `OnboardEventQueue` is a
bounded queue that drops the oldest event when it is full and counts the drops
in `dropped`, the way [`DeviceWatcher` bounds its
iterator](discovery.md#watching-devices-continuously).

```python
from lifx.onboard import OnboardEvent, OnboardEventQueue


def show(event: OnboardEvent) -> None:
    print(event.type.name, event.phase and event.phase.name, event.ssid)


result = await onboard(network, scanner=scanner, joiner=joiner, on_event=show)

events = OnboardEventQueue(maxsize=64)
result = await onboard(network, scanner=scanner, joiner=joiner, events=events)
events.close()
async for event in events:
    print(event.type.name, event.took)
print("dropped:", events.dropped)
```

An `OnboardEvent` is a frozen dataclass with the `type` (`SCANNING`,
`DISCOVERED`, `JOINING`, `JOINED`, `WAITING_FOR_SOFTAP`, `ON_SOFTAP`,
`DIALING`, `CONFIGURED`, `REJOINING`, `REJOINED`, `VERIFYING`, `VERIFIED` or
`FAILED`), the `phase`, and whichever of `serial`, `ssid`, `address`,
`networks`, `timeout`, `took` and `error` apply. It has no field for the
password. The loop over a queue ends once `close()` has been called and the
queue is empty; the library never closes a queue it was given, so one queue can
serve several runs.

## Results and errors

`onboard()` returns a `Result`, a frozen dataclass:

| Field | Meaning |
|-------|---------|
| `serial` | The device onboarded |
| `verified` | Whether the device was seen on the LAN afterwards |
| `took` | Seconds the run took |
| `phase` | The phase that failed; `None` on success |
| `error` | The failure; `None` on success |
| `host_network` | The network the host ended on: the SSID a successful `joiner.rejoin()` targeted, or the network a `CurrentNetworkReporter` saw the host land on through auto-join. `None` only when the host never got back |

It raises on failure, and the exception carries the same `Result` as its
`result` attribute, so you can choose either style.

```python
from lifx.onboard import LifxOnboardError, OnboardPhase, SoftApNotFoundError

try:
    result = await onboard(network, scanner=scanner, joiner=joiner, target="8274eb")
except SoftApNotFoundError:
    print("No SoftAP with that serial; is the device in setup mode?")
except LifxOnboardError as error:
    print(error.phase, error.result and error.result.took)
else:
    assert result.phase is None or isinstance(result.phase, OnboardPhase)
```

Every exception derives from `LifxOnboardError`, itself a `LifxError`:

| Exception | Phase | Raised when |
|-----------|-------|-------------|
| `SoftApNotFoundError` | `SCAN` | No matching SoftAP appeared within `FIND_TIMEOUT` |
| `SoftApJoinError` | `JOIN` | The host could not join the SoftAP in time |
| `SoftApWaitTimeoutError` | `WAIT` | The SoftAP never accepted a TCP probe |
| `HostLeftSoftApError` | `WAIT` | The host was found on another network while waiting |
| `SoftApUnreachableError` | `DIAL` | A plain TCP probe of the SoftAP did not connect |
| `SoftApDialError` | `DIAL` | The TCP connect or TLS handshake failed |
| `SoftApSendError` | `CONFIGURE` | Writing the credential message failed |
| `HostRejoinError` | `REJOIN` | The host could not be returned to any target |
| `VerifyTimeoutError` | `VERIFY` | The device was not seen on the LAN in time |
| `InvalidSoftApTargetError` | none | The target is not a SoftAP name, serial or suffix |
| `LegacyTlsUnavailableError` | none | The host's OpenSSL refuses the TLS 1.0 configuration |
| `MissingCredentialsError` | none | A secured network was given with no password (also a `ValueError`) |

On a macOS host an empty scan usually means the operating system redacted the
results, and `SoftApNotFoundError` says so. Pass the full SoftAP name as the
target to skip the scan.

A `VerifyTimeoutError` is not a failed handoff. Its `Result` still says the
device was configured and the host rejoined; only the sighting on the LAN is
missing.

## Verifying on the LAN

The last phase confirms the device arrived. It listens to a
[`DeviceWatcher`](discovery.md#watching-devices-continuously) and succeeds on
the first `ADDED` or `UPDATED` event for the device's serial whose address is
not the SoftAP address. This is *onboarding verification*: it asks whether the
device is now reachable on your network, and is distinct from the watcher's
liveness tracking, which asks whether a known device is still answering.

Three rules follow from that:

- Only events emitted after verification begins count. The watcher's existing
  record for the serial is deliberately ignored, because a record left over
  from before the reset would be a false positive.
- A sighting at the SoftAP address (`172.16.0.1` by default, compared as an IP
  address) is ignored. A device first seen there and then at its LAN address
  is one `UPDATED` event with an address change, and that counts.
- Nothing is sent to the device; the watcher's discovery does the looking.

By default (`verify=True`) the library opens its own watcher for the
verification window, with UDP discovery only, and closes it afterwards. To
share a watcher with the rest of your application, or to add the mDNS leg for
devices that join over Thread, pass your own running watcher. It is left
running afterwards.

```python
from lifx import DeviceWatcher

async with DeviceWatcher(mdns=True) as watcher:
    result = await onboard(
        network,
        scanner=scanner,
        joiner=joiner,
        target="d073d58274eb",
        verify=watcher,
    )
```

Pass `verify=False` to stop after the rejoin. The `Result` then has
`verified=False` and you must confirm the device some other way.

## Onboarding many devices

`bulk_onboard()` is the same sequence in a loop. It scans every
`scan_interval` seconds, and for each LIFX SoftAP it has not yet attempted it
runs join, wait, dial, configure and rejoin exactly as `onboard()` does, one
device at a time, because the host has a single WiFi interface. It is an async
generator that yields one `Result` per attempt.

```python
import contextlib

from lifx.onboard import bulk_onboard

async with contextlib.aclosing(
    bulk_onboard(network, scanner=scanner, joiner=joiner, targets=["8274eb", "61a0c3"])
) as results:
    async for result in results:
        print(result.serial, "verified" if result.verified else result.phase)
```

A failed device yields a `Result` with `phase` and `error` set, and the loop
continues; `bulk_onboard()` never raises for one device. The run ends when:

- every serial in `targets` has been attempted. `targets` is an allow-list of
  serials or suffixes; every other SoftAP is ignored. One never seen is
  yielded last as a `SCAN` phase `SoftApNotFoundError` result;
- `max_devices` attempts have been made, successful or not;
- `stop_when_idle_for` seconds of scanning have passed with no new serial. The
  clock is paused while a device is being attempted, so a long handoff never
  counts as idle; or
- the consuming task is cancelled, in which case host recovery runs for the
  device in flight.

With none of `targets`, `max_devices` or `stop_when_idle_for` the loop runs
until cancelled. A serial is attempted once, however often it reappears.

```python
async with DeviceWatcher() as watcher:
    async with contextlib.aclosing(
        bulk_onboard(network, scanner=scanner, joiner=joiner, max_devices=2, verify=watcher)
    ) as results:
        async for result in results:
            print(result.serial, result.verified, result.took)
```

Verification is interleaved. Once a device is configured it starts listening
for that serial, and the wait for it to appear on the LAN runs in the
background while the loop scans for the next device. One watcher serves the
whole run: your own, left running, or a library-owned one opened before the
first attempt and closed when the run ends. Results are therefore yielded in
*completion order*, not scan order, and pending verifications are drained
after the loop ends.

Always wrap the generator in `contextlib.aclosing()` if you might `break` out
of the loop. Without it the generator stays open until it is garbage
collected, and a library-owned watcher keeps running meanwhile.

## Security

The SoftAP's TLS connection runs with certificate verification off. LIFX
devices present self-signed certificates with no trust anchor and nothing in
the subject that binds the certificate to a serial, so there is nothing to
verify against. In effect the channel trusts the open network the host joined.

That has a consequence worth stating plainly: someone running a look-alike
`LIFX xxxxxx` SoftAP within radio range while you onboard could receive the
home network credentials. To reduce the risk:

- Pass the full SoftAP name or the serial as the target, so a SoftAP that is
  not the device you meant is never joined. Avoid `target=None` anywhere other
  than a place you control.
- Onboard with no other devices in setup mode nearby.
- If onboarding was attempted on a SoftAP you did not expect, treat the home
  network password as exposed and change it.

## What lifx-async does not ship

lifx-async owns the protocol, the TLS client, the state machine and the
verification. It ships no `Scanner` or `Joiner`, no host WiFi backend and no
command line tool. Those need subprocesses, `ctypes`, `pyobjc` or an app
bundle, none of which belongs in a library with no dependencies, so they live
in a separate project that depends on lifx-async and not the other way round.
Its contract with this library is exactly the one on this page:

- It implements `Scanner` and `Joiner` per platform, and as many of the three
  capabilities as the platform allows.
- It builds `SoftApNetwork` values with `SoftApNetwork.from_ssid()`, which
  derives the serial through `Serial.from_softap_ssid()`.
- It calls `onboard()` or iterates `bulk_onboard()` with a `HomeNetwork` built
  from a password it read from standard input, the environment or a no-echo
  prompt, never from `argv`.
- It renders `OnboardEvent` values and maps `Result.phase` to its own exit
  codes.
- It may pass its own `DeviceWatcher` or leave `verify=True`.

If you are building a backend and need something this contract does not give
you, that is a change to lifx-async, so open an issue.

## Hardware verification status

The sequence follows rules learned on real devices, but the library has not
yet been run against a factory-reset device of every generation. Five
questions are open, tracked in issue #334. Until they are answered the package
should be treated as unreleased, and which products it supports is not yet
established.

| Gate | Question | Status |
|------|----------|--------|
| 1 | Which current products still expose a SoftAP and accept packet 305 over TLS | Pending |
| 2 | Whether TLS 1.2 is accepted by every firmware that still has a SoftAP, or `legacy_tls` is needed more often than "before 2020" suggests | Pending |
| 3 | Whether packets 304 (`GetAccessPoints`) and 306 (`StateAccessPoint`) still answer over the TLS channel | Pending |
| 4 | What a device does with an SSID or password longer than its field (lifx-async rejects them whatever the device does) | Pending |
| 5 | Whether the SoftAP name carries the serial suffix or the MAC suffix on firmware 3.70 and later, where the two differ by one in the last octet | Pending |

The package is not released until gates 1, 2 and 5 are answered. Gates 3 and 4
inform this page and follow-up work but do not block release.
