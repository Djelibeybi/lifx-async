# DISC-04: WiFi Staleness Control Evidence

**Recorded:** 2026-09-08

## What this settles

v2.0 Phase 14 (THREAD-04) recorded one Thread-arm staleness trial with no control: a Thread
device's mDNS advertisement outlived its own power loss by an interval of 4140 to 4200 seconds
(confirmed absent at poll 70 of a sixty-second poll cadence, `first_absence_poll: 70`,
`confirmed_expiry_poll: 72`), and the device took 69.4 seconds to answer both discovery legs
again after power returned. Both `.planning/ROADMAP.md` and `.planning/REQUIREMENTS.md`
subsequently described "69s" as a disappearance-to-expiry figure. It was not: 69.4 seconds is
the *restoration* duration, measured from the power-on edge, and the disappearance-to-expiry
figure is the 4140 to 4200 second interval above, measured from power-off. This document settles
both halves of DISC-04: it reports the WiFi control trial's own four figures, corrects the
conflated wording at every site that carries it, and states the verdict the control exists to
answer.

## The instrument

Both arms ran through `.planning/scripts/thread_revalidation.py`'s `staleness` subcommand:

```
uv run .planning/scripts/thread_revalidation.py staleness \
    --session-dir 17-EVIDENCE --alias-map <operator-private-path> \
    --alias <alias> --power-off <script> --power-on <script> \
    [--confound background_pollers --confound busy_network \
     --confound unquiesced_environment --confound wireless_interference]
```

R5's frozen protocol is identical across both arms: the sixty-second absolute poll cadence
(`STALENESS_POLL_INTERVAL_S`), the three consecutive both-legs-absent confirmation rule
(`STALENESS_CONFIRM_ABSENT_POLLS`), and the three-hour cap (`STALENESS_CAP_S`) all live in
`measurement_support.py`, which no change authorised for this phase touched, and both arms'
manifests assert those same three values. That frozen core is the argument for calling this a
control at all.

It is not, however, a fully protocol-matched pair, and this document says so rather than
presenting the two runs as a matched control. SPEC amendment A8 authorised four departures in
`thread_revalidation.py` before the WiFi arm ran, none touching R5's frozen constants: an
explicit 45 second discovery timeout passed at the call site rather than the library's 15 second
default, needed because the fleet is roughly 66 devices on a contested network; each poll now
records measured wall-clock `elapsed_s` rather than `poll_index * interval_s`, because a
fully-absent poll runs both discovery legs sequentially and can overrun the 60 second interval;
restoration now closes on the first discovery leg present, bounded, with both legs recorded
separately (`restoration_discover_s`, `restoration_mdns_s`), rather than blocking on both; and
the manifest inventory schema now accepts `InfraredLight` and `HevLight`. The WiFi arm also
carried four confounders the Thread arm carried none of: `background_pollers`, `busy_network`,
`unquiesced_environment` and `wireless_interference`. This is a comparison arm against the Thread
trial, not a protocol-matched control, and the verdict below is bounded accordingly.

The WiFi session's files carry the tool's own hardcoded `14-` filename prefix inside this
directory (`17-EVIDENCE/14-MANIFEST.json`, `17-EVIDENCE/14-STALENESS.jsonl`) even though this is
Phase 17's own evidence: the constants at `.planning/scripts/thread_revalidation.py:310-321` are
not parameterised by session, and the resume path reads them back by that literal name. The
mismatch between the filename prefix and the phase number is expected, not an error.

## The four figures

| Figure | Value | Measurement resolution | Arm |
|---|---|---|---|
| Disappearance-to-expiry | 4140 to 4200 s | Sixty-second poll cadence; poll 69 (elapsed 4140 s) still present, poll 70 (elapsed 4200 s) first confirmed absent | Thread |
| Restoration duration | 69.4 s | The tool's own nanosecond clock (69.35774216699065 s) | Thread |
| Disappearance-to-expiry | at most 80.8548 s (rounded to 80.85 s elsewhere in this document) | Measured wall-clock completion of the confirming poll (poll 1 of `17-EVIDENCE/14-STALENESS.jsonl`), not the nominal 60 s cadence: `first_absence_poll: 1` means the device was already gone by the time poll 1's two discovery legs finished, so the bound is the real elapsed time that poll took rather than a multiple of the nominal interval | WiFi |
| Restoration duration | 14.6 s (mDNS leg; broadcast leg 15.5 s) | The tool's own nanosecond clock; present-detection short-circuits on match, so each restoration poll took roughly a second rather than the ~90 s an absent poll can cost | WiFi |

Both Thread figures are derivable from the committed Phase 14 row. The disappearance interval
comes from the start of the confirming three-poll absence run, `confirmed_expiry_poll` 72 minus
the three-poll confirmation rule plus one, giving poll 70, and therefore the interval between poll
69's elapsed time (4140 s) and poll 70's (4200 s); it does not come from `first_absence_poll`
alone, which happens to equal 70 in this particular run but would not in a run with an earlier
transient absence. The restoration figure is `restoration_duration_s`, 69.35774216699065, quoted
throughout the project as 69.4 seconds.

The WiFi figures are read the same way from the committed row in `17-EVIDENCE/14-STALENESS.jsonl`,
with one difference the row itself explains: `first_absence_poll: 1` and `confirmed_expiry_poll: 3`
put the confirming run's start at poll 1, so there is no earlier present-poll boundary to anchor a
lower bound on, and the correct claim is a bound rather than an interval. Because the WiFi arm
records measured wall-clock `elapsed_s` per poll (SPEC amendment A8, point 2), that bound is the
actual measured completion time of poll 1, 80.8548 seconds, not the nominal cadence figure a
`poll_index * interval_s` calculation would produce (60 s). The nominal figure would have been
wrong here: a fully-absent poll runs both discovery legs sequentially at a 45 second timeout each,
so it can and did take longer than the nominal 60 second interval to complete. Restoration is read
from `restoration_duration_s` (14.557117625008686 s, the mDNS leg, which closed first) and
`restoration_discover_s` (15.530575042008422 s, the broadcast leg), quoted to one decimal place as
14.6 s and 15.5 s.

## The verdict

**Mechanism.** A WiFi bulb has no Thread Border Router rebroadcasting its mDNS records on its
behalf, so nothing sustains a stale WiFi advertisement the way a border router sustains a stale
Thread one. That absence of a rebroadcasting intermediary is why the WiFi advertisement was
already gone by the first poll, at most 80.8548 seconds after power loss, while the Thread
advertisement persisted for 4140 to 4200 seconds, roughly two orders of magnitude longer.

That order-of-magnitude difference supports treating the Thread arm's lingering advertisement as
**Thread-specific** (an SRP-registration and border-router artefact) rather than a **general mDNS
TTL or goodbye-message artefact** common to any mDNS-advertised device on this network: a general
artefact would be expected to produce a WiFi lingering time on the same order as the Thread one,
and it did not.

The observation that **would have supported the opposite verdict** is a WiFi advertisement
lingering on the same order of magnitude as the Thread arm's 4140 to 4200 second interval, named
here in advance of stating the result so this reasoning cannot be read as retrofitted to it. It
did not happen: the WiFi advertisement was already confirmed absent at the first poll.

One trial per arm establishes a direction, not a distribution. It cannot distinguish, on the
Thread side, a genuine SRP lease of roughly seventy minutes from an OpenThread default of 7200
seconds sampled mid-renewal-cycle, and it cannot rule out that a different WiFi device, a
different border router firmware, or a different network condition would produce a different
WiFi figure. Settling either question needs repeated trials, which are explicitly out of scope
for this phase.

### Precision limits on the WiFi figures

The operator required this caveat to travel forward into this document, verbatim in substance.
The WiFi figures above are not measurements of a precise value, for four reasons:

1. The 60 second poll cadence is coarser than the phenomenon it measured. A disappearance that
   completed inside 80.8548 seconds means the measurement's resolution is roughly the size of the
   thing being measured, and because `first_absence_poll: 1`, nothing about the shape of the
   disappearance inside that first window was observed.
2. Each poll runs both discovery legs sequentially at a 45 second timeout, so an absent poll costs
   roughly 90 seconds of wall time and cannot resolve anything finer than that.
3. Four confounders were present on the WiFi arm that the Thread arm carried none of:
   `background_pollers`, `busy_network`, `unquiesced_environment` and `wireless_interference`.
4. The arms are neither protocol-matched (the four SPEC amendment A8 departures above) nor
   condition-matched (the confounder asymmetry in point 3).

**What the evidence supports:** the order-of-magnitude difference in disappearance-to-expiry
(roughly two orders of magnitude, 4140 to 4200 s against at most 80.8548 s), and the restoration
figures, which are better resolved than the disappearance figure (present-detection short-circuits
on match, so those polls each took roughly a second rather than the ~90 second cost of an absent
poll), though still measured under all four confounders above.

**What the evidence does not support:** any point value for the WiFi disappearance-to-expiry
figure, any claim about where inside 0 to 80.8548 seconds the disappearance actually happened, or
any precise magnitude comparison between the two arms beyond "roughly two orders of magnitude
apart".

A third round is planned, using a 1 Hz disappearance measurement against a targeted unicast probe
rather than a broadcast sweep, because a sweep's absence verdict costs a full discovery timeout
per poll and cannot be driven at 1 Hz. That round supersedes the WiFi disappearance figure only;
it does not supersede the restoration figures above, which are already well resolved.

**The Thread arm, the WiFi arm and the pair together are not a guarantee, a lease value, a universal limit, or a tuning input for any library constant.** This mirrors the discipline v2.0
Phase 14 (THREAD-04) held when it refused to call 4200 seconds a lease.
