This request is reversed rather than implemented.

The probe named in this issue is operator tooling: a hardware measurement script an operator
runs by hand against real Thread devices, not code the shipped library or CI executes. Phase 15
of the v2.1 milestone states that as a general rule in `AGENTS.md`'s new "Measured Tree" section:
coverage measures the shipped library plus any code a CI job executes, and nothing else. Adding
the probe to coverage collection would have broken that rule rather than served it, since nothing
in CI runs the probe.

The probe has relocated to `.planning/scripts/ipv6_thread_probe.py`, alongside the repository's
other operator hardware tooling, and stays outside the measured tree entirely. Its coverage
percentage is no longer a project question.

`pyproject.toml`'s `--cov` targets are now exactly `lifx` and `generate_theme_data`.

Closing on this reasoning.
