---
seed: 001
planted_during: v1.1 Wire Reliability (2026-07-16)
trigger_when: LIFX Thread firmware is released (expected soon after 2026-07)
---

# SEED-001: Revalidate wire reliability over Thread/IPv6

## The Idea

When LIFX ships Thread firmware, re-run the v1.1 reliability validation over Thread/IPv6:
discovery coverage, retry behaviour, and animation flow control were all measured and
tuned on WiFi/IPv4 UDP.

## Why This Matters

Every wire-reliability finding from the 2026-07-16 spike series is WiFi-specific:

- **Discovery**: the median-48/73 single-broadcast failure was attributed to per-AP
  broadcast delivery at DTIM. Thread has no APs and no 255.255.255.255 broadcast —
  discovery likely moves to mDNS/IPv6 multicast with entirely different loss behaviour.
  The escalating re-broadcast schedule may be unnecessary or need retuning.
- **Power save**: the gen4 sub-250 ms wake tail is ESP32 WiFi modem-sleep behaviour.
  Thread is designed for sleepy end devices — latency shape will differ.
- **Ack RTT assumptions**: the 200 ms "acked bulb answers by now" constant and the
  ack-gated flow-control tuning (~100 ms ack RTT under streaming load, 2-outstanding
  gate) were measured on WiFi. Thread's mesh hop latency and lower throughput may need
  different gates — or make 20 FPS streaming infeasible entirely.
- **IPv6 transport**: `UdpTransport` is `AF_INET` only (`socket.AF_INET`,
  `transport.py:141-145`). Thread devices are IPv6-first; the network layer needs an
  AF_INET6 path before any of this can even be tested.

## When to Surface

- LIFX announces or ships Thread firmware for any device family
- A milestone touches the network layer's address-family assumptions
- mDNS discovery work is planned (Thread devices will likely be mDNS-discoverable first)
