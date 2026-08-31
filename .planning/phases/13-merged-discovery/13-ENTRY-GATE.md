# Phase 13 Merged Discovery Entry Gate

## Pre-merge revision

`c484a023f4190a746367b4b6cca3db57d20e068c`

This revision predates the merged discovery coordinator. At this gate,
`discover()` still delegates exclusively to `discover_udp()`, and
`discover_udp()` owns the established direct UDP discovery path.

## Automated gate

The following focused selection ran against the pre-merge revision:

```text
uv run --frozen pytest -o addopts='' tests/test_api/test_api_discovery.py tests/test_network/test_discovery_rebroadcast.py tests/test_network/test_discovery_errors.py tests/test_scripts/test_measure_merged_discovery.py -q
```

Result: **117 passed**. This covers the public UDP entry contract, inherited
source and serial validation, first-wins duplicate handling, timeout and idle
window behaviour, generator closure, error cleanup, the private observation
scope, and the measurement harness.

The canonical baseline row was then appended with:

```text
uv run --frozen scripts/measure_merged_discovery.py --mode baseline-only --environment emulator --rounds 1 --quiescence quiesced --output .planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl
```

Result: **one schema-valid baseline row** with a positive unique count, only
known synthetic aliases, `direct_udp` implementation provenance, UDP-only
source contributions, and the categorical `owned_loopback_dynamic` target.

## Emulator ownership and teardown

The harness owned one in-process emulator for the entire measurement. It
requested an operating-system-assigned endpoint, propagated the verified
non-zero bound port to the server and all existing device states, added a
second device after binding, and verified StateService advertisements before
the timed arm began. The endpoint value remained process-local and is not
present in tracked evidence. The asynchronous context completed server
shutdown before the command returned; focused failure and cancellation tests
also verified that shutdown and private-source finalisation complete before
control escapes.

## Value-suppressed tuning check

The following value-suppressed comparison against the pre-plan parent revision
`fd269efb663e348b01f2e0c089266897babfa52f` returned no differences:

```text
git diff --exit-code fd269efb663e348b01f2e0c089266897babfa52f c484a023f4190a746367b4b6cca3db57d20e068c -- src/lifx/const.py src/lifx/network/connection.py src/lifx/animation src/lifx/effects
```

Therefore the established rebroadcast, idle, discovery timeout, request retry,
bandwidth, and animation tuning values are unchanged at the entry gate.

## Privacy check

The tracked JSONL contains aliases, source categories, categorical target
provenance, monotonic timings, counts, and the committed revision only. It
contains no numeric endpoint, raw device identifier, hostname, packet, TXT
content, or exception text.
