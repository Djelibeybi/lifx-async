# Onboarding

`lifx.onboard` takes a LIFX device that is not on your network, joins its own
setup access point (SoftAP), hands it your home network's credentials, and
confirms it arrived. Import it explicitly: nothing here is exported from the
top-level `lifx` namespace. The [onboarding guide](../user-guide/onboarding.md)
explains the sequence and how the pieces fit together; this page is the
reference.

```python
from lifx.onboard import HomeNetwork, onboard
```

lifx-async ships no implementation of `Scanner` or `Joiner`. Joining a host to
a WiFi network needs subprocesses, `ctypes` or an app bundle, so those live
outside this library.

## Entry points

::: lifx.onboard.onboard
    options:
      heading_level: 3

::: lifx.onboard.bulk_onboard
    options:
      heading_level: 3

## Networks

::: lifx.onboard.HomeNetwork
    options:
      heading_level: 3

::: lifx.onboard.SoftApNetwork
    options:
      heading_level: 3

## Host WiFi protocols

The caller supplies a `Scanner` and a `Joiner`. The three capabilities after
them are optional and are found at runtime with `isinstance`; the `Joiner` is
consulted before the `Scanner` for each one.

::: lifx.onboard.Scanner
    options:
      heading_level: 3

::: lifx.onboard.Joiner
    options:
      heading_level: 3

::: lifx.onboard.CurrentNetworkReporter
    options:
      heading_level: 3

::: lifx.onboard.NetworkForgetter
    options:
      heading_level: 3

::: lifx.onboard.Disassociator
    options:
      heading_level: 3

## SoftAP control channel

::: lifx.onboard.SoftApClient
    options:
      heading_level: 3

::: lifx.onboard.SoftApConnection
    options:
      heading_level: 3

::: lifx.onboard.build_access_point_message
    options:
      heading_level: 3

::: lifx.onboard.softap.SOFTAP_ADDRESS
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.softap.SOFTAP_PORT
    options:
      heading_level: 3
      show_source: false

## Events

::: lifx.onboard.OnboardPhase
    options:
      heading_level: 3

::: lifx.onboard.OnboardEvent
    options:
      heading_level: 3

::: lifx.onboard.OnboardEventType
    options:
      heading_level: 3

::: lifx.onboard.OnboardEventQueue
    options:
      heading_level: 3

## Results

::: lifx.onboard.Result
    options:
      heading_level: 3

## Exceptions

Every exception derives from `LifxOnboardError`, which is a `LifxError`. Each
carries the `phase` that failed and, once a run has started, the `result` that
describes it. `LifxOnboardError` and each subclass below appear with the phase
it normally reports.

```
LifxError
└── LifxOnboardError
    ├── MissingCredentialsError (also a ValueError)
    ├── InvalidSoftApTargetError   (no phase)
    ├── LegacyTlsUnavailableError  (no phase)
    ├── SoftApNotFoundError        (SCAN)
    ├── SoftApJoinError            (JOIN)
    ├── SoftApWaitTimeoutError     (WAIT)
    ├── HostLeftSoftApError        (WAIT)
    ├── SoftApUnreachableError     (DIAL)
    ├── SoftApDialError            (DIAL)
    ├── SoftApSendError            (CONFIGURE)
    ├── HostRejoinError            (REJOIN)
    └── VerifyTimeoutError         (VERIFY)
```

::: lifx.onboard.LifxOnboardError
    options:
      heading_level: 3

::: lifx.onboard.MissingCredentialsError
    options:
      heading_level: 3

::: lifx.onboard.InvalidSoftApTargetError
    options:
      heading_level: 3

::: lifx.onboard.LegacyTlsUnavailableError
    options:
      heading_level: 3

::: lifx.onboard.SoftApNotFoundError
    options:
      heading_level: 3

::: lifx.onboard.SoftApJoinError
    options:
      heading_level: 3

::: lifx.onboard.SoftApWaitTimeoutError
    options:
      heading_level: 3

::: lifx.onboard.HostLeftSoftApError
    options:
      heading_level: 3

::: lifx.onboard.SoftApUnreachableError
    options:
      heading_level: 3

::: lifx.onboard.SoftApDialError
    options:
      heading_level: 3

::: lifx.onboard.SoftApSendError
    options:
      heading_level: 3

::: lifx.onboard.HostRejoinError
    options:
      heading_level: 3

::: lifx.onboard.VerifyTimeoutError
    options:
      heading_level: 3

## Timing defaults

The defaults were tuned on hardware. Pass a different value to `onboard()` or
`bulk_onboard()` only when you have measured a reason to.

::: lifx.onboard.machine.FIND_TIMEOUT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.FIND_POLL
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.WAIT_TIMEOUT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.WAIT_POLL
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.DIAL_TIMEOUT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.REJOIN_TIMEOUT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.REJOIN_POLL
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.AUTO_JOIN_WAIT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.VERIFY_TIMEOUT
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.machine.VERIFY_POLL
    options:
      heading_level: 3
      show_source: false

::: lifx.onboard.bulk.SCAN_INTERVAL
    options:
      heading_level: 3
      show_source: false

## Serial helpers

::: lifx.onboard.serials.parse_serial
    options:
      heading_level: 3

::: lifx.onboard.serials.serial_from_softap_ssid
    options:
      heading_level: 3

::: lifx.protocol.models.LIFX_OUI
    options:
      heading_level: 3
      show_source: false

## Packet 305 types

`WifiInterface` and `WifiSecurity` are re-exported from `lifx.onboard` for
convenience; the protocol layer defines them.

::: lifx.protocol.protocol_types.WifiInterface
    options:
      heading_level: 3

::: lifx.protocol.protocol_types.WifiSecurity
    options:
      heading_level: 3
