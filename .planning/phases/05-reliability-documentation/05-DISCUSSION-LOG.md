# Phase 5: Reliability Documentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 5-reliability-documentation
**Areas discussed:** Placement & navigation, Wake-tail depth (DOCS-01), Streaming guidance shape (DOCS-02), Coverage breadth

---

## Placement & navigation

| Option | Description | Selected |
|--------|-------------|----------|
| New dedicated page (Recommended) | Single new User Guide page holding all reliability content with cross-links | |
| Extend existing pages | Streaming guidance into animation.md; wake-tail into troubleshooting.md/faq.md | ✓ |
| Hybrid | New page for overview + wake-tail; streaming into animation.md | |

**User's choice:** Extend existing pages

| Option | Description | Selected |
|--------|-------------|----------|
| Troubleshooting + FAQ entry (Recommended) | Full section in troubleshooting.md plus short FAQ entry linking to it | ✓ |
| Troubleshooting only | One home, no FAQ duplication | |
| FAQ only | Question-shaped answer in faq.md | |

**User's choice:** Troubleshooting + FAQ entry

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted cross-links (Recommended) | ceiling-lights.md → wake-tail; animation.md ↔ troubleshooting wake-tail | ✓ |
| Host pages only | No extra links | |
| Broad linking | Also api/animation.md, api/devices.md, quickstart | |

**User's choice:** Targeted cross-links

---

## Wake-tail depth (DOCS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Concise + key numbers (Recommended) | Behaviour, sub-250 ms figure, when it matters, what to do; no methodology | ✓ |
| Full spike story | Include Spike 001 measurement context | |
| Minimal footnote | 2–3 sentences | |

**User's choice:** Concise + key numbers

| Option | Description | Selected |
|--------|-------------|----------|
| Concrete recipe (Recommended) | Code snippet with interval sourced from Spike 001 findings | ✓ |
| Qualitative only | Trade-off explanation without interval or code | |
| Recipe without interval | Pattern in code, readers pick their own interval | |

**User's choice:** Concrete recipe

| Option | Description | Selected |
|--------|-------------|----------|
| Symptom-first (Recommended) | Lead with the symptom; no precise generation identification | |
| Firmware/product guidance | Concrete identification via product families / firmware versions | ✓ |
| Both | Symptom-first plus identification note | |

**User's choice:** Firmware/product guidance

| Option | Description | Selected |
|--------|-------------|----------|
| Admonition callout (Recommended) | Visible note: no keepalive daemon by design + why | ✓ |
| Inline sentence | Lower visual weight | |

**User's choice:** Admonition callout

---

## Streaming guidance shape (DOCS-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Narrative + don't-list + example (Recommended) | What the layer handles, do-not-reimplement list, minimal streaming-loop example | ✓ |
| Do/don't list only | Prescriptive bullets, no example | |
| Narrative only | Prose without lists or examples | |

**User's choice:** Narrative + don't-list + example

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with numbers (Recommended) | ~20 FPS ceiling; Capsule 16×8 sustains ~10 FPS; stutter = latest-frame-wins | ✓ |
| Yes, qualitative | Packets-per-frame reasoning without numbers | |
| No | No FPS guidance | |

**User's choice:** Yes, with numbers

| Option | Description | Selected |
|--------|-------------|----------|
| Behavioural contract (Recommended) | Observable behaviour only; skip tuning constants | ✓ |
| Full mechanism | Also probe placement, gate threshold, expiry | |
| Minimal | One sentence | |

**User's choice:** Behavioural contract

---

## Coverage breadth

| Option | Description | Selected |
|--------|-------------|----------|
| Stale-content audit (Recommended) | DOCS-01/02 new content + fix stale claims in existing prose pages; no overview | ✓ |
| Strictly DOCS-01/02 | Only the two required items | |
| Add v1.1 overview too | Short reliability overview somewhere sensible | |

**User's choice:** Stale-content audit

| Option | Description | Selected |
|--------|-------------|----------|
| Prose pages only (Recommended) | docs/ markdown only; docstrings untouched | ✓ |
| Prose + docstrings | Also audit src/ docstrings describing wire behaviour | |

**User's choice:** Prose pages only

---

## Claude's Discretion

- Section headings, placement/ordering within host pages, admonition type/wording
- Code example style (match existing docs conventions)
- FAQ addition as one entry or two

## Deferred Ideas

None — discussion stayed within phase scope.
