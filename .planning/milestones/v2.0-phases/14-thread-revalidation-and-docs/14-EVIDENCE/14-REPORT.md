# Phase 14 Thread Revalidation Report

Generated solely from validated append-only JSONL journals via `generate_summary()`. Never hand-edited.

## Discovery coverage (THREAD-01)

- `discover`: rounds attempted [1, 2, 3, 4, 5, 6], 8 device(s) observed.
- `discover_mdns`: rounds attempted [1, 2, 3, 4, 5, 6], 8 device(s) observed.

## Request timing (THREAD-02)

These are this fleet's and this session's observations, taken on a mesh
with recorded confounders. They are not an authoritative benchmark, a
universal Thread limit, a regression gate, or sufficient grounds for
tuning any library constant. Each row's environmental qualification is
the `confounders` field on its journal entries.

- `LIFX-Candle-C-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 44352583.5, 'p95_ns': 70898959, 'max_ns': 126050667}; ack_rtt={'count': 100, 'median_ns': 44071604.5, 'p95_ns': 70718375, 'max_ns': 125882542}.
- `LIFX-Ceiling-13x26-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 56947333.5, 'p95_ns': 146568542, 'max_ns': 287808000}; ack_rtt={'count': 100, 'median_ns': 56411042.0, 'p95_ns': 134552000, 'max_ns': 287616583}.
- `LIFX-DL-Intl-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 39732187.5, 'p95_ns': 67238333, 'max_ns': 236034333}; ack_rtt={'count': 100, 'median_ns': 39271708.0, 'p95_ns': 66669333, 'max_ns': 126004833}.
- `LIFX-DL-Intl-2`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 39707875.0, 'p95_ns': 80335208, 'max_ns': 326974334}; ack_rtt={'count': 100, 'median_ns': 39504854.5, 'p95_ns': 71194584, 'max_ns': 326801209}.
- `LIFX-Luna-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 47853333.0, 'p95_ns': 94467000, 'max_ns': 241985250}; ack_rtt={'count': 100, 'median_ns': 47683583.0, 'p95_ns': 94306250, 'max_ns': 241823250}.
- `LIFX-Mini-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 44963187.5, 'p95_ns': 91108417, 'max_ns': 133450666}; ack_rtt={'count': 100, 'median_ns': 44505646.0, 'p95_ns': 90942709, 'max_ns': 132937583}.
- `LIFX-Mini-2`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 38309500.0, 'p95_ns': 74954792, 'max_ns': 273634250}; ack_rtt={'count': 100, 'median_ns': 37891437.5, 'p95_ns': 74752708, 'max_ns': 273186250}.
- `LIFX-Tube-1`: outcomes {'completed': 100}; logical_latency={'count': 100, 'median_ns': 45022042.0, 'p95_ns': 62446958, 'max_ns': 274426417}; ack_rtt={'count': 100, 'median_ns': 44650937.5, 'p95_ns': 62178750, 'max_ns': 273991084}.

## Animation (THREAD-03, out of scope)

Thread animation is a recorded scope boundary, not a measurement this
phase completes. Thread does not have the bandwidth to sustain animation
at usable or smooth frame rates, and pushing that volume of data onto a
mesh is poor practice regardless of what a measurement would show.
`Animator` is intended to be locked to WiFi devices in a future
milestone. Class closure does not consult animation at all.

Any observation below shows only that Thread carried the frames without
failing. It is NOT evidence that Thread animation is usable, and it is
not a throughput, pacing, ACK-delivery, smoothness, parity or
performance result. The frame payload in use sends one identical
brightness-0 frame per call, so firmware that short-circuits an
unchanged frame does almost no work; the counters below cannot be read
as rendering behaviour.

- `LIFX-Candle-C-1`: restored=True restoration_verified=False; rates=[{'fps': 1, 'outcome': 'completed', 'offered': 11, 'packets_sent': 11, 'gated': 0, 'failed': 0}, {'fps': 2, 'outcome': 'completed', 'offered': 21, 'packets_sent': 21, 'gated': 0, 'failed': 0}, {'fps': 5, 'outcome': 'completed', 'offered': 51, 'packets_sent': 51, 'gated': 0, 'failed': 0}].

## Advertisement staleness (THREAD-04)

- `LIFX-Ceiling-13x26-1`: {'disposition': 'confirmed_expiry', 'first_absence_poll': 70, 'confirmed_expiry_poll': 72, 'restored_available_ns': 162593033821416, 'restoration_duration_s': 69.35774216699065}

## Six-class ledger (THREAD-05)

- `CeilingLight`: evidence_backed -- {'disposition': 'evidence_backed', 'aliases': ['LIFX-Ceiling-13x26-1'], 'gap_reason': None, 'gap_recorded_date': None}
- `HevLight`: named_gap -- {'disposition': 'named_gap', 'aliases': [], 'gap_reason': "no Thread-capable hardware of this class in the fleet; the fleet's devices of this class predate Thread", 'gap_recorded_date': '2026-09-04'}
- `InfraredLight`: named_gap -- {'disposition': 'named_gap', 'aliases': [], 'gap_reason': "no Thread-capable hardware of this class in the fleet; the fleet's devices of this class predate Thread", 'gap_recorded_date': '2026-09-04'}
- `Light`: evidence_backed -- {'disposition': 'evidence_backed', 'aliases': ['LIFX-DL-Intl-1', 'LIFX-DL-Intl-2', 'LIFX-Mini-1', 'LIFX-Mini-2'], 'gap_reason': None, 'gap_recorded_date': None}
- `MatrixLight`: evidence_backed -- {'disposition': 'evidence_backed', 'aliases': ['LIFX-Candle-C-1', 'LIFX-Luna-1'], 'gap_reason': None, 'gap_recorded_date': None}
- `MultiZoneLight`: evidence_backed -- {'disposition': 'evidence_backed', 'aliases': ['LIFX-Tube-1'], 'gap_reason': None, 'gap_recorded_date': None}
