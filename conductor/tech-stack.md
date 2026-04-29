# Tech Stack: lifx-async

## Language

- **Python 3.10+** (tested on 3.11, 3.12, 3.13, 3.14)

## Framework

- None — pure asyncio library, no web or backend framework

## Database

- None — stateless library

## Infrastructure

- **Distribution:** PyPI (latest published v5.2.0; project version v5.4.8)
- **CI/CD:** GitHub Actions
- **Release:** python-semantic-release with Conventional Commits

## Key Dev Dependencies

- **Testing:** pytest, pytest-asyncio, pytest-cov, lifx-emulator-core
- **Linting/Formatting:** ruff (line-length 88, select E/F/I/N/W/UP)
- **Type Checking:** pyright (standard mode, Python 3.10 target)
- **Documentation:** Zensical, mkdocstrings-python, llmstxt-standalone
- **Build:** hatchling

## Package Management

- **uv** exclusively (no pip, poetry, or conda)
