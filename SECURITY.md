# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 5.x     | Yes                |
| < 5.0   | No                 |

Only the latest release in the current major version receives security updates.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via [GitHub Security Advisories](https://github.com/Djelibeybi/lifx-async/security/advisories/new).

You should receive an acknowledgement within 72 hours. If the vulnerability is confirmed, a fix will
be developed privately and released as a patch version as soon as practical.

## Scope

This library communicates with LIFX devices over the local network using UDP. The following areas
are considered in scope for security reports:

- **Protocol parsing**: Buffer overflows, out-of-bounds reads, or crashes when handling malformed
  packets in the serializer or header parser
- **Input validation**: Insufficient validation of data received from the network (packet sizes,
  field values, serial numbers)
- **Denial of service**: Vulnerabilities that allow a malicious device or actor on the local network
  to crash or hang the library (e.g., resource exhaustion via crafted responses)
- **Dependency chain**: Issues introduced through development dependencies that could affect the
  published library (note: the library has zero runtime dependencies)

## Out of Scope

- **LIFX device firmware vulnerabilities**: Report these directly to [LIFX](https://www.lifx.com)
- **Local network attacks**: This library assumes the local network is trusted, consistent with the
  LIFX protocol design (unencrypted UDP). Attacks requiring a privileged network position (e.g.,
  ARP spoofing) are out of scope
- **Rate limiting and device overload**: The library intentionally does not implement rate limiting;
  this is the application developer's responsibility

## Security Considerations for Users

- This library uses **unencrypted UDP** on the local network, as specified by the LIFX protocol.
  Do not expose LIFX device traffic to untrusted networks.
- The library enforces **maximum packet size limits** (`MAX_PACKET_SIZE = 1024`) and **minimum
  packet size validation** (`MIN_PACKET_SIZE = 36`) to mitigate oversized or malformed packet
  attacks.
- Discovery responses are validated against **source ID** and **serial number** to prevent response
  spoofing.
