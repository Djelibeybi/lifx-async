# Quick Task 260726-42c: MAC/serial correlation audit script — Research

**Researched:** 2026-07-26
**Domain:** lifx-async diagnostics / macOS ARP / Rich CLI output
**Confidence:** HIGH (all library claims verified against source in this session; ARP behaviour verified live on this Mac; PEP 723 mechanics verified by executed experiment)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Report **both** MACs: `derived_mac` (from `Device.get_mac_address()`) and `real_mac` (OS ARP table), plus a **verdict** column: `identical` / `off-by-one` / `mismatch` / `unknown`.
- Rich table by default (colour-coded verdict, summary panel grouping by product + firmware); Rich progress indicator during the sweep.
- `--csv` flag emits *only* CSV on stdout — no Rich chrome or progress on stdout.
- Columns: serial, derived_mac, real_mac, verdict, product_id, product_name, firmware major.minor, IP.
- `rich` declared via **PEP 723 inline metadata only** — must NOT touch `pyproject.toml`.
- Broadcast `discover()` sweep, no filters.
- Location: `scripts/`, run with `uv run scripts/<name>.py`.

### Claude's Discretion
- Script filename; ARP invocation mechanics (macOS primary, Linux bonus); concurrency approach and per-device timeout/failure handling; CLI flag names beyond `--csv`.

### Deferred Ideas
- None recorded.
</user_constraints>

## Summary

Everything needed is already in the library. `discover()` yields ready-to-use `Device` objects (serial/IP as `str`), two unicast requests per device (`get_version()` + `get_host_firmware()`) produce product id, firmware and the derived MAC, and `lifx.products.get_product(pid).name` gives the product name. The independent observation comes from one `arp -an` snapshot parsed after the sweep — verified live on this host: macOS prints **non-zero-padded** MAC octets, so both MACs must be normalised before comparison.

**Primary recommendation:** query each yielded device directly (no `async with` — it costs 7 requests instead of 2), bound concurrency with `asyncio.Semaphore(16)`, snapshot `arp -an` once after all queries, and send all Rich chrome to `Console(stderr=True)` so `--csv` stdout stays clean.

**Critical trap found by experiment:** a PEP 723 script run with `uv run` executes in an **isolated environment — the project's `lifx` package is NOT importable** unless the metadata declares `lifx-async` with a `[tool.uv.sources]` path entry pointing at the local checkout. Verified both ways (see §PEP 723).

## lifx-async API surface (all [VERIFIED: src in this session])

### discover()

`src/lifx/api.py:747` — async generator yielding `Device` subclasses:

```python
async def discover(
    timeout: float = DISCOVERY_TIMEOUT,            # 15.0 (const.py:28)
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,  # 1.0
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,  # 4.0
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,  # 16.0 (const.py:42)
    max_retries: int = DEFAULT_MAX_RETRIES,           # 8 (const.py:46)
) -> AsyncGenerator[Device, None]:
```

- Internally calls `discovered.create_device()` per response (`discovery.py:60-123`): creates a temp `Device`, runs `ensure_capabilities()` (GetVersion + GetHostFirmware unicast), closes the temp connection, then yields a **fresh** instance of the right subclass. Consequence 1: **the yielded device has no cached state** — the script must re-query. Consequence 2: discovery alone already sends unicast traffic to every device, which populates the ARP table. Consequence 3: `create_device()` swallows all exceptions and returns `None` → `discover()` silently skips devices that answered the broadcast but failed the follow-up queries. Devices that never respond simply don't appear — the dataset only covers responders (document this limitation in output).
- `device_timeout`/`max_retries` are passed into every yielded device. For a fleet sweep, pass lower values (e.g. `device_timeout=5.0, max_retries=3`) so a straggler doesn't hold a concurrency slot for the default 16 s.

### Per-device fields

| Need | Access | Type / evidence |
|------|--------|-----------------|
| serial | `device.serial` | `str`, 12-hex normalised via `Serial.from_string(...).to_string()` (`base.py:421`) — never bytes |
| IP | `device.ip` | `str`, set in `__init__` (`base.py:422`) — no need to touch `DiscoveredDevice` |
| product id | `(await device.get_version()).product` | `DeviceVersion(vendor: int, product: int)` (`base.py:957,44-53`) |
| firmware | `await device.get_host_firmware()` | `FirmwareInfo(build: int, version_major: int, version_minor: int)` (`base.py:92-104,1077`) |
| derived MAC | `await device.get_mac_address()` → `str` like `"d0:73:d5:01:02:03"` (zero-padded, lowercase, `base.py:666-683`) | see below |
| product name | `from lifx.products import get_product; get_product(pid).name` | `ProductInfo(pid, name, vendor, capabilities, ...)` (`registry.py:39-56`); note `get_product()` at module level returns `ProductInfo` (raises/hands back registry entry), fields `pid: int`, `name: str` |

`get_mac_address()` (`base.py:666-683`): derives octets from `self.serial`, applies `octets[5] = (octets[5] + 1) % 256` **iff `firmware.version_major == 3`**, caches in `_mac_address`. It fetches host firmware itself if not already cached, so call order is safe; conversely `get_host_firmware()` triggers the MAC calculation automatically (`base.py:1110-1111`), so after `await device.get_host_firmware()` the `device.mac_address` property is already populated. **Minimum per-device traffic: exactly 2 requests** (`get_version()` + `get_host_firmware()`).

### Connection pattern

Do **not** use `async with device:` — `__aenter__` → `_initialize_state()` runs a 7-request gather (label, power, both firmwares, location, group, version) (`base.py:1671-1721`). The library's own `create_device()` demonstrates the lean pattern (`discovery.py:100-121`): call methods directly (connection lazy-opens), then `await device.connection.close()` in a `finally:` block.

## ARP lookup — macOS (primary), verified live on this host

`arp` read access needs no root (`/usr/sbin/arp` is `r-xr-xr-x`). Output captured this
session, with every address replaced by a private-range placeholder — the line shapes and
octet padding below are verbatim, the addresses are not:

```
$ arp -an
? (192.168.1.137) at 0:0:5e:0:53:f8 on en0 [ethernet]
? (192.168.1.254) at (incomplete) on en0 [ethernet]
? (192.168.1.1) at 00:00:5e:00:53:e on en0 ifscope [ethernet]
? (192.168.1.1) at 00:00:5e:00:53:e on en1 ifscope [ethernet]

$ arp -n 192.168.1.99     # absent entry
192.168.1.99 (192.168.1.99) -- no entry     # exit code 1
```

Confirmed facts:
- **Octets are NOT zero-padded**: `00:00:5e:00:53:e`, `0:0:5e:0:53:f8`. The derived MAC IS zero-padded (`f"{octet:02x}"`). Comparing raw strings silently mismatches — **normalise both sides**: `":".join(f"{int(o, 16):02x}" for o in mac.split(":"))`.
- Unresolved entries print `at (incomplete)`; a wholly absent IP prints `-- no entry` with exit code 1. Both → verdict `unknown`.
- **The same IP can appear on multiple lines** (multi-interface hosts: `192.168.1.1` on en0 and en1 above). Take the first line with a parseable MAC.
- Parse rule for `arp -an` lines: `re.match(r"\S+ \((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+) ", line)`; `(incomplete)` fails the MAC group naturally.

**Recommended approach:** ONE `arp -an` subprocess call after all device queries complete, parsed into a `dict[ip, mac]` — not 73 per-IP invocations. macOS keeps reachable entries ~20 minutes [ASSUMED — expiry timing from training; irrelevant to correctness since we read seconds after querying]; the per-device unicast requests during discovery + the script's own 2 queries guarantee the entry is fresh. No stdlib alternative worth using on macOS: reading the ARP table natively requires `sysctl(CTL_NET, PF_ROUTE, ..., NET_RT_FLAGS, RTF_LLINFO)` via ctypes — hand-rolled routing-socket parsing for zero benefit. Shell out via `asyncio.create_subprocess_exec("arp", "-an")` or plain `subprocess.run` (it's a single call after the async phase; sync is fine).

**Linux (bonus)** [ASSUMED — standard, but not verified this session]: read `/proc/net/arp` with stdlib `open()` — whitespace-separated columns `IP address, HW type, Flags, HW address, Mask, Device`; `Flags 0x0` = incomplete, MAC there IS zero-padded. Fallback `ip -4 neigh show`. Gate on `sys.platform`.

## PEP 723 inline metadata — verified by executed experiments

**Experiment 1 (isolation trap):** a script with a PEP 723 block declaring only `rich`, run with `uv run` from the project root → `lifx importable: NO (No module named 'lifx')`, `rich version: 15.0.0`. uv runs inline-metadata scripts in an isolated env, ignoring the project.

**Experiment 2 (the fix):** placed in `scripts/`, this exact block resolved `lifx` to the **local checkout** (`lifx from: /Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/__init__.py`) and installed rich 15.0.0:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=15.0.0", "lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../", editable = true }
# ///
```

Relative `path` resolves relative to the script's directory (proven: `../` from `scripts/` hit the repo root). The local-source pin is **mandatory** — a bare `lifx-async` dependency would install the PyPI release and test the *published* `get_mac_address()`, not the code under test. `requires-python = ">=3.10"` matches `pyproject.toml:6`. Nothing is added to `pyproject.toml`, satisfying the locked decision.

Note: `scripts/mdns_probe.py` has **no** PEP 723 block — it relies on the project env and degrades gracefully when `lifx` is missing. The new script inverts that: with the block above, `lifx` is always importable, so no `HAVE_LIFX` fallback is needed.

Minor: `rich.__version__` does not exist in rich 15.x (AttributeError observed); use `importlib.metadata.version("rich")` if a version print is ever wanted.

## Rich patterns [CITED: context7.com/textualize/rich; version VERIFIED: PyPI JSON]

- **Latest version: `rich` 15.0.0** (published 2026-04-12, PyPI JSON verified this session). Pin `rich>=15.0.0` per "always use the latest version".
- **stderr routing (the CSV-cleanliness key):** `err_console = Console(stderr=True)` directs all output to `sys.stderr`; `Console(quiet=True)` suppresses everything. Idiom for this script:
  - One `Console(stderr=True)` owns the Progress bar in **both** modes (stderr never pollutes a stdout pipe).
  - Human mode: results `Table`/`Panel` printed via a default stdout `Console`.
  - `--csv` mode: use stdlib `csv.writer(sys.stdout)` — no Rich object ever touches stdout.
- **Progress driven from asyncio:** `Progress(console=err_console, transient=True)` as a context manager; `task = progress.add_task("Querying devices", total=None)` (total unknown until discovery ends — bump with `progress.update(task, total=n)` as devices arrive) and `progress.advance(task)` after each device completes. Calling `advance()` from coroutines on one event loop is safe (single-threaded).
- **Per-cell colour:** markup strings in `add_row`, e.g. `table.add_row(serial, derived, real, "[green]identical[/green]")` — or precompute `{"identical": "green", "off-by-one": "yellow", "mismatch": "bold red", "unknown": "dim"}`.
- **Summary panel:** `console.print(Panel(renderable, title="Correlation by product + firmware"))` — a nested `Table` grouped by (product_name, fw major.minor) → verdict counts is the natural renderable.

## Concurrency & failure isolation

- Connections are per-device (each `Device.__init__` creates its own `DeviceConnection`, `base.py:428`), so cross-device parallelism is native. The ~20 msg/sec limit is **per device**; this script sends only 2 messages per device, so the constraint is host-side burst/socket pressure, not device rate.
- **Recommend `asyncio.Semaphore(16)`** around the per-device probe. Rationale: 73 devices ÷ 16 concurrent × ~0.1-0.3 s per healthy probe ≈ seconds; with `device_timeout=5.0, max_retries=3`, a dead slot clears in ≤5 s, keeping worst-case sweep bounded, while 16 concurrent UDP sockets is trivial for the host.
- **Failure isolation:** wrap each per-device probe body in `try/except LifxError as e:` (all library errors derive from `LifxError`) producing a row with `verdict="unknown"` and the error noted; collect with `asyncio.gather(*tasks)` where each task cannot raise (exceptions converted to rows inside), or `gather(..., return_exceptions=True)` as a backstop. Always `await device.connection.close()` in `finally`.
- Devices can be consumed and queried as `discover()` yields them (start tasks inside the `async for`), overlapping the 15 s discovery window with querying.
- Known project fact [VERIFIED: STATE.md]: single discovery rounds under-count (6-round median 48/73 in Spike 005). One round is acceptable for this correlation script (a partial sample still correlates), but note in `--help`/epilog that re-runs enlarge the dataset.

## Verdict computation (planner note)

Two distinct comparisons exist; the locked verdict classifies **serial → real_mac**:
- `identical`: normalised(real) == normalised(serial-as-mac)
- `off-by-one`: real differs from serial only in octet 5 by `+1 % 256`
- `mismatch`: neither
- `unknown`: no/incomplete ARP entry or device query failed

`derived_mac` vs `real_mac` equality is then the *rule-correctness* check (derived should equal real iff the `version_major == 3` branch is right for that device) — cheap to show implicitly since both columns are printed side by side.

## Common Pitfalls

1. **Unpadded macOS ARP octets** — silent 100%-mismatch bug if compared raw. Normalise both sides (evidence above).
2. **PEP 723 isolation** — without `[tool.uv.sources]` the script tests PyPI lifx-async, not the local checkout, invalidating the whole exercise (proven by experiment).
3. **`async with device:`** costs 7 requests/device instead of 2 — ~365 extra packets across the fleet for nothing.
4. **Rich on stdout in `--csv` mode** — keep Progress on `Console(stderr=True)` always; CSV via stdlib `csv` module only.
5. **Duplicate ARP lines per IP** (multi-interface) — take first complete entry.
6. **Default `device_timeout=16.0` / `max_retries=8`** would let one dead device stall a semaphore slot ~16 s; pass lower values into `discover()`.
7. **CLAUDE.md str-not-bytes rule** — already satisfied: `device.serial` is normalised `str`, `get_mac_address()` returns `str`.

## Package Legitimacy Audit

| Package | Registry | Verdict | Disposition |
|---------|----------|---------|-------------|
| rich 15.0.0 | PyPI (JSON API verified this session, published 2026-04-12, Textualize) | OK | Approved — PEP 723 only, never pyproject.toml |
| lifx-async | local checkout via `[tool.uv.sources]` | OK | The project itself |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | macOS ARP reachable-entry lifetime ~20 min | ARP | Nil — script reads seconds after unicast exchange |
| A2 | Linux `/proc/net/arp` format & `ip neigh` fallback | ARP (bonus) | Low — Linux is explicitly a bonus, gate on `sys.platform` and degrade to `unknown` |
| A3 | Firmware generations map roughly gen2=2.x, gen3=3.x, gen4=4.x | context only | None — script records raw `version_major`, doesn't interpret |

## Sources

- **HIGH:** `src/lifx/api.py`, `src/lifx/devices/base.py`, `src/lifx/network/discovery.py`, `src/lifx/products/registry.py`, `src/lifx/const.py`, `pyproject.toml` (read this session); live `arp -an`/`arp -n` output on this macOS host; two executed `uv run` PEP 723 experiments; PyPI JSON API for rich.
- **MEDIUM:** Context7 rendered Rich docs (textualize/rich) for `Console(stderr=True)`, `Progress(console=...)`, Table markup, Panel. (ctx7 CLI quota was exceeded; docs fetched from context7.com directly.)
- **Research date:** 2026-07-26. Valid until: ~2026-08-26 (stable domain; re-check rich latest version at implementation time).
