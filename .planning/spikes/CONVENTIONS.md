# Spike Conventions

Patterns and stack choices established across spike sessions. New spikes follow these
unless the question requires otherwise.

## Stack

- Plain Python scripts run with `uv run python .planning/spikes/NNN-name/<script>.py`,
  importing lifx-async's own internals (`UdpTransport`, `create_message`,
  `parse_message`, `allocate_source`) rather than reimplementing the protocol.
- No third-party dependencies; stdlib only on top of the repo package.

## Structure

- One directory per spike: `NNN-name/{README.md, <verb>.py, results-*.jsonl, summary-*.json}`.
- Scripts take a `run` subcommand with `--quick` for a cheap shakedown before the full
  run. Always shakedown first — every full run in this series was preceded by a shakedown
  that caught at least one harness bug.
- Long runs go in background; nothing else may touch the network while a spike collects
  data (traffic contaminates timing/loss measurements).

## Patterns

- **EventLog**: JSONL event stream (one dict per event, ts + category) appended live,
  plus an aggregated `summary-*.json` and a stdout table at the end.
- **Loss/randomness injection**: `random.Random(f"spike-NNN:{key}")` seeded per cell for
  reproducibility; never bare `random`.
- **Single-shot probes**: measure with retries disabled — library retry budgets mask the
  losses being counted.
- **Real hardware**: use the quiesced System Test devices (see memory/project fleet
  note); alternate A/B conditions per trial to control for network drift; stagger
  concurrent per-bulb runs by a few seconds.
- **Percentiles**: `sorted(vals)[min(len-1, ceil(len*p)-1)]` — the truncating form
  under-reports at small n (bug found in spike 001).
- Response `label` fields from packet unpacking are already `str` (library convention) —
  don't `rstrip(b"\x00")`.

## Repo quirks

- prek hooks reformat spike scripts (ruff-format) and fix EOF newlines on JSON/HTML —
  expect one commit retry after generating artefacts.
- bandit runs on `.planning/` too: `# nosec` with justification for subprocess/`except
  Exception: continue` patterns in harnesses.
- Never commit a `results-*.jsonl` that a background run is still appending to.
