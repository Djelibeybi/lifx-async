# Phase 11 API Coverage Decision

No external API integration: Phase 11 hardens the repository's existing, dependency-free LAN
mDNS/DNS-SD implementation. It adds no external SDK, hosted service, authenticated endpoint,
webhook, cloud API, account, secret, or dashboard configuration. RFC 6762 is a protocol authority,
not an integrated service. The phase therefore has no INTEGRATE/OPT-OUT capability matrix and no
external user setup.

The supported public Python surface does change: `Device.connectivity` is added and the documented
low-level mDNS record/generator names are deliberately internalised. Those are repository API
contracts governed by MDNS-02 and MDNS-08, not external API integrations.
