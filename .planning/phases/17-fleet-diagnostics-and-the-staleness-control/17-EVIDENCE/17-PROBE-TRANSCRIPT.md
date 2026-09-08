# MDNS-10: Thread-fleet probe hardware evidence

**Recorded:** 2026-09-08

## The instrument

Command, run from the repository root with the Thread fleet powered and advertising:

```
set -o pipefail
uv run .planning/scripts/ipv6_thread_probe.py --stage records \
  --alias-map PATH-OUTSIDE-THIS-REPOSITORY.json \
  | tee SCRATCH-PATH-OUTSIDE-THIS-REPOSITORY/17-probe-stdout.txt
echo "probe-exit=$?"
```

**Git revision:** `50063fab244fca07d50b7ede09be26e9417e61b6`

**Probe exit status:** 0

## What the hardware did and did not produce

AC-11 requires this section to state plainly which of the new output elements the hardware
run produced and which it did not, rather than letting a reader infer that every new state was
demonstrated on the day.

- refused-state CHOSEN line: not observed. Would have needed: an instance whose SRV target had at least one cached address record, none of which had routable scope, so the selector rejects every candidate and prints CHOSEN with the refused-state reason. Every one of the 23 instances in this sweep resolved to a usable record.
- absent-state CHOSEN line: not observed. Would have needed: an SRV target for which no address record was cached at all inside the discovery window, so the selector has nothing to choose from. The summary block below reports `awaiting address records : 0`, meaning this state did not occur.
- unused-fallback line: not observed. Would have needed: an instance exhibiting the refused or absent state above, with a packet-source address also present and unused; this line only renders beneath one of those two states, and neither occurred in this run.
- malformed-TXT line: not observed. Would have needed: a device emitting a TXT payload that fails to parse, so its serial, product and firmware fields print as unavailable. This sweep reported 59 LIFX-bearing packets and 0 malformed.
- new summary counts: observed. Both split lines from D-03 are present, `cached but no usable address : 0` and `awaiting address records : 0`, and the pre-existing counter D-03 replaced (`chose a bare link-local addr`) does not appear, which is the positive evidence that this transcript comes from the changed probe rather than the pre-phase one.

## Transcript

```
========================================================================
STAGE 1: mDNS records and address selection
========================================================================
Queried from local port 49802 (legacy unicast)
Packets: 59 received, 59 LIFX-bearing, 0 malformed
Responding sources: 192.0.2.1, 192.0.2.2, 192.0.2.3, 192.0.2.4, 192.0.2.5, 192.0.2.6, 192.0.2.7, 192.0.2.8, 192.0.2.9, 192.0.2.10, 192.0.2.11, 192.0.2.12, 192.0.2.13, 192.0.2.14, 192.0.2.15, 192.0.2.16, 192.0.2.17

23 service instance(s):

------------------------------------------------------------------------
  instance : LIFX-Switch-1._lifx._udp.local
  serial   : LIFX-Switch-1
  product  : 89 (LIFX Switch)
  firmware : 4.100
  SRV      : LIFX-Switch-1.local:56700
  A        : 192.0.2.1  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::1  [link-local]
             2001:db8:1::1  [GUA]
             2001:db8:3::1  [ULA]
  CHOSEN   : 192.0.2.1  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Switch-2._lifx._udp.local
  serial   : LIFX-Switch-2
  product  : 89 (LIFX Switch)
  firmware : 4.100
  SRV      : LIFX-Switch-2.local:56700
  A        : 192.0.2.7  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::2  [link-local]
             2001:db8:1::2  [GUA]
             2001:db8:3::2  [ULA]
  CHOSEN   : 192.0.2.7  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Switch-3._lifx._udp.local
  serial   : LIFX-Switch-3
  product  : 89 (LIFX Switch)
  firmware : 4.100
  SRV      : LIFX-Switch-3.local:56700
  A        : 192.0.2.14  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::3  [link-local]
             2001:db8:1::3  [GUA]
             2001:db8:3::3  [ULA]
  CHOSEN   : 192.0.2.14  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Path-19-98._lifx._udp.local
  serial   : LIFX-Path-19-98
  product  : 173 (LIFX Path)
  firmware : 4.112
  SRV      : LIFX-Path-19-98.local:56700
  A        : 192.0.2.17  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::4  [link-local]
             2001:db8:3::4  [ULA]
             2001:db8:1::4  [GUA]
  CHOSEN   : 192.0.2.17  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Neon-Outdoor-23ce-6528-147a-e9c0-00010000._lifx._udp.local
  serial   : LIFX-Neon-Outdoor-23ce-6528-147a-e9c0
  product  : 161 (LIFX Neon Outdoor)
  firmware : 4.200
  SRV      : C23F4958C363F7B6.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::5  [ULA]
  CHOSEN   : 2001:db8:3::5  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Path-19-15._lifx._udp.local
  serial   : LIFX-Path-19-15
  product  : 174 (LIFX Path)
  firmware : 4.112
  SRV      : LIFX-Path-19-15.local:56700
  A        : 192.0.2.6  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::5  [link-local]
             2001:db8:3::6  [ULA]
             2001:db8:1::5  [GUA]
  CHOSEN   : 192.0.2.6  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Path-19-129._lifx._udp.local
  serial   : LIFX-Path-19-129
  product  : 173 (LIFX Path)
  firmware : 4.112
  SRV      : LIFX-Path-19-129.local:56700
  A        : 192.0.2.5  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::6  [link-local]
             2001:db8:3::7  [ULA]
             2001:db8:1::6  [GUA]
  CHOSEN   : 192.0.2.5  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-A21-18-3-00000000._lifx._udp.local
  serial   : LIFX-A21-18-3
  product  : 169 (LIFX A21)
  firmware : 4.200
  SRV      : LIFX-A21-18-3.local:56700
  A        : 192.0.2.2  [IPv4]
  AAAA     : 2 record(s)
             2001:db8:4::7  [link-local]
             2001:db8:1::7  [GUA]
  CHOSEN   : 192.0.2.2  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Candle-C-943b-7fe3-a70e-6304-00010000._lifx._udp.local
  serial   : LIFX-Candle-C-943b-7fe3-a70e-6304
  product  : 215 (LIFX Candle C)
  firmware : 4.200
  SRV      : E6B61881B2A6C30C.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::8  [ULA]
  CHOSEN   : 2001:db8:3::8  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Tube-d1dd-d3c-2219-6119-00010000._lifx._udp.local
  serial   : LIFX-Tube-d1dd-d3c-2219-6119
  product  : 217 (LIFX Tube)
  firmware : 4.200
  SRV      : 420A03EB2D314A18.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::9  [ULA]
  CHOSEN   : 2001:db8:3::9  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-A21-18-67-00000000._lifx._udp.local
  serial   : LIFX-A21-18-67
  product  : 170 (LIFX A21)
  firmware : 4.200
  SRV      : LIFX-A21-18-67.local:56700
  A        : 192.0.2.3  [IPv4]
  AAAA     : 2 record(s)
             2001:db8:4::8  [link-local]
             2001:db8:1::8  [GUA]
  CHOSEN   : 192.0.2.3  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-A21-19-224-00000000._lifx._udp.local
  serial   : LIFX-A21-19-224
  product  : 170 (LIFX A21)
  firmware : 4.200
  SRV      : LIFX-A21-19-224.local:56700
  A        : 192.0.2.13  [IPv4]
  AAAA     : 2 record(s)
             2001:db8:4::9  [link-local]
             2001:db8:1::9  [GUA]
  CHOSEN   : 192.0.2.13  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Ceiling-13x26-19-231-00010000._lifx._udp.local
  serial   : LIFX-Ceiling-13x26-19-231
  product  : 201 (LIFX Ceiling 13x26)
  firmware : 4.200
  SRV      : 2E165FD197D70843.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::a  [ULA]
  CHOSEN   : 2001:db8:3::a  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Path-Intl-19-185._lifx._udp.local
  serial   : LIFX-Path-Intl-19-185
  product  : 222 (LIFX Path Intl)
  firmware : 4.112
  SRV      : LIFX-Path-Intl-19-185.local:56700
  A        : 192.0.2.10  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::a  [link-local]
             2001:db8:3::b  [ULA]
             2001:db8:1::a  [GUA]
  CHOSEN   : 192.0.2.10  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Luna-19-182-00010001._lifx._udp.local
  serial   : LIFX-Luna-19-182
  product  : 219 (LIFX Luna)
  firmware : 4.200
  SRV      : 3E46774BFA724470.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::c  [ULA]
  CHOSEN   : 2001:db8:3::c  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Mini-bbb1-1b33-8ad1-d453-00010000._lifx._udp.local
  serial   : LIFX-Mini-bbb1-1b33-8ad1-d453
  product  : 182 (LIFX Mini)
  firmware : 4.200
  SRV      : FAAF9CFE7AB46C6E.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::d  [ULA]
  CHOSEN   : 2001:db8:3::d  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Mini-ef95-4e1d-fa24-99b4-00010000._lifx._udp.local
  serial   : LIFX-Mini-ef95-4e1d-fa24-99b4
  product  : 182 (LIFX Mini)
  firmware : 4.200
  SRV      : 5295E98E748B9205.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::e  [ULA]
  CHOSEN   : 2001:db8:3::e  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Ceiling-19-82-00020002._lifx._udp.local
  serial   : LIFX-Ceiling-19-82
  product  : 177 (LIFX Ceiling)
  firmware : 4.200
  SRV      : LIFX-Ceiling-19-82.local:56700
  A        : 192.0.2.16  [IPv4]
  AAAA     : 2 record(s)
             2001:db8:4::b  [link-local]
             2001:db8:1::b  [GUA]
  CHOSEN   : 192.0.2.16  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-DL-Intl-18-95-00010001._lifx._udp.local
  serial   : LIFX-DL-Intl-18-95
  product  : 224 (LIFX DL Intl)
  firmware : 4.200
  SRV      : F62C48BBA987ED57.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::f  [ULA]
  CHOSEN   : 2001:db8:3::f  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-DL-Intl-18-189-00010000._lifx._udp.local
  serial   : LIFX-DL-Intl-18-189
  product  : 224 (LIFX DL Intl)
  firmware : 4.200
  SRV      : DE70B31EE009AB2E.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::10  [ULA]
  CHOSEN   : 2001:db8:3::10  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-DL-Intl-19-158-00010000._lifx._udp.local
  serial   : LIFX-DL-Intl-19-158
  product  : 224 (LIFX DL Intl)
  firmware : 4.200
  SRV      : 028E70F024E538FA.local:56700
  A        : (none)
  AAAA     : 1 record(s)
             2001:db8:3::11  [ULA]
  CHOSEN   : 2001:db8:3::11  [ULA]
  WHY      : routable ULA preferred over link-local

------------------------------------------------------------------------
  instance : LIFX-Beam-19-183._lifx._udp.local
  serial   : LIFX-Beam-19-183
  product  : 120 (LIFX Beam)
  firmware : 4.13
  SRV      : LIFX-Beam-19-183.local:56700
  A        : 192.0.2.9  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::c  [link-local]
             2001:db8:1::c  [GUA]
             2001:db8:3::12  [ULA]
  CHOSEN   : 192.0.2.9  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
  instance : LIFX-Beam-19-200._lifx._udp.local
  serial   : LIFX-Beam-19-200
  product  : 120 (LIFX Beam)
  firmware : 4.13
  SRV      : LIFX-Beam-19-200.local:56700
  A        : 192.0.2.12  [IPv4]
  AAAA     : 3 record(s)
             2001:db8:4::d  [link-local]
             2001:db8:1::d  [GUA]
             2001:db8:3::13  [ULA]
  CHOSEN   : 192.0.2.12  [IPv4]
  WHY      : A record present; IPv4 preferred over IPv6

------------------------------------------------------------------------
Summary:
  instances with an A record    : 13
  instances with AAAA record(s) : 23
  resolved to a usable record   : 23
  cached but no usable address  : 0
  awaiting address records      : 0
```
