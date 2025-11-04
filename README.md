# lifx-async

A modern, type-safe, async Python library for controlling LIFX smart devices over the local network.

[![CI](https://github.com/Djelibeybi/lifx-async/workflows/CI/badge.svg)](https://github.com/Djelibeybi/lifx-async/actions/workflows/ci.yml)
[![Codecov](https://codecov.io/gh/Djelibeybi/lifx-async/branch/main/graph/badge.svg)](https://codecov.io/gh/Djelibeybi/lifx-async)
[![Docs](https://github.com/Djelibeybi/lifx-async/workflows/Documentation/badge.svg)](https://Djelibeybi.github.io/lifx-async/)

[![Python](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13%20|%203.14-blue)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/lifx-async)](https://pypi.org/project/lifx-async/)
[![License](https://img.shields.io/badge/license-UPL--1.0-blue)](https://opensource.org/license/UPL)



## Features

- **📦 No Runtime Dependencies**: only Python standard libraries required
- **🎯 Type-Safe**: Full type hints with strict Pyright validation
- **⚡ Async Context Managers**: Provides `async with` and `await` usage patterns
- **🔌 Connection Pooling**: Efficient reuse with LRU cache
- **🏗️ Layered Architecture**: Protocol → Network → Device → API
- **🔄 Protocol Generator**: generates LIFX protocol `Packets`, `Fields` and `Enum` classes from LIFX public protocol definition
- **🌈 Comprehensive Support**: supports all LIFX smart lighting products including Color, White, Warm to White, Filament, Clean, Night Vision, Z, Beam, String, Neon, Permanent Outdoor, Tile, Candle, Ceiling, Path, Spot, and Luna.


## License

Licensed under the [Universal Permissive License v1.0](https://opensource.org/license/UPL).

Copyright &copy; 2025 Avi Miller &lt;me@dje.li&gt;
