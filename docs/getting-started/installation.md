# Installation

## System Requirements

- **Python**: 3.11 or higher
- **Network**: Local network access to LIFX devices
- **OS**: Linux, macOS, Windows

## Installation Methods

### Using uv (Recommended)

[`uv`](https://github.com/astral-sh/uv) is a fast Python package installer and resolver written in
Rust. It's significantly faster than pip and is the recommended installation method:

```bash
uv pip install lifx-async
```

If you don't have `uv` installed yet:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### Using pip

If you prefer to use pip:

```bash
pip install lifx-async
```

### From Source

For the latest development version:

```bash
git clone https://github.com/Djelibeybi/lifx-async.git
cd lifx

# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### With Development Dependencies

To install with development tools (recommended for contributors):

```bash
git clone https://github.com/Djelibeybi/lifx-async.git
cd lifx

# Using uv (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"
```

## Verify Installation

Test that lifx-async is installed correctly:

```python
import lifx

print(lifx.__version__)
```

Or run a quick discovery:

```python
import asyncio
from lifx import discover


async def main():
    async with discover(timeout=3.0) as group:
        print(f"Found {len(group)} devices")
        for device in group:
            label = await device.get_label()
            print(f"  - {label}")


asyncio.run(main())
```

## Troubleshooting

### Import Error

If you see `ModuleNotFoundError: No module named 'lifx'`:

1. Ensure lifx-async is installed: `uv pip list | grep lifx-async` or `pip list | grep lifx-async`
1. Check your Python version: `python --version`
1. Verify you're using the correct Python environment

### Network Discovery Issues

If discovery doesn't find devices:

1. Ensure LIFX devices are on the same network
1. Check firewall settings allow UDP broadcasts
1. Try increasing the timeout: `discover(timeout=10.0)`
1. Use direct connection if you know the IP: `Light.from_ip("192.168.1.100")`

### Permission Errors

On some systems, you may need elevated permissions for network operations:

```bash
# Linux/macOS
sudo python your_script.py

# Or add your user to the appropriate group
sudo usermod -a -G netdev $USER  # Linux
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Start controlling your lights
- [API Reference](../api/index.md) - Complete API documentation
- [FAQ](../faq.md) - Frequently asked questions
