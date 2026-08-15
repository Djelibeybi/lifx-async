# lifx-async

A modern, type-safe, async Python library for controlling LIFX smart devices over the local network.

[![CI](https://github.com/Djelibeybi/lifx-async/workflows/CI/badge.svg)](https://github.com/Djelibeybi/lifx-async/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/Djelibeybi/lifx-async/branch/main/graph/badge.svg)](https://codecov.io/gh/Djelibeybi/lifx-async)
[![Docs](https://github.com/Djelibeybi/lifx-async/workflows/Documentation/badge.svg)](https://Djelibeybi.github.io/lifx-async/)

[![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/lifx-async)](https://pypi.org/project/lifx-async/)
[![License](https://img.shields.io/badge/license-UPL--1.0-blue)](https://opensource.org/license/UPL)



## Features

- **📦 No Runtime Dependencies**: only Python standard libraries required
- **🎯 Type-Safe**: Full type hints, validated with Pyright
- **⚡ Async Context Managers**: Provides `async with` and `await` usage patterns
- **🔍 Dual Discovery**: UDP broadcast plus zero-dependency mDNS/DNS-SD discovery
- **🏗️ Layered Architecture**: Protocol → Network → Device → API
- **🔄 Protocol Generator**: generates LIFX protocol `Packets`, `Fields` and `Enum` classes from LIFX public protocol definition
- **✨ Built-in Effects**: 26 software effects plus 166 colour themes, filtered by device capability
- **🎞️ Animation Layer**: high-frequency frame delivery for real-time multizone and matrix effects
- **🌈 Comprehensive Support**: supports all LIFX smart lighting products — see the [device classes](https://djelibeybi.github.io/lifx-async/api/devices/) documentation


## License

Licensed under the [Universal Permissive License v1.0](https://opensource.org/license/UPL).

Copyright &copy; 2025, 2026 Avi Miller &lt;me@dje.li&gt;
