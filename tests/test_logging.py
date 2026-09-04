"""The library must not emit log output unless the application asks for it.

Python's ``logging`` HOWTO tells library authors to attach a
``NullHandler`` to the library's top-level logger so that a warning raised
before the application configures logging is swallowed rather than written
to stderr by the ``lastResort`` handler. Every ``lifx.*`` module logs through
``logging.getLogger(__name__)``, so a single handler on the ``lifx`` logger
covers the whole package.
"""

from __future__ import annotations

import logging

import pytest

import lifx  # noqa: F401  # importing the package attaches the handler


def test_package_logger_has_null_handler() -> None:
    """The top-level ``lifx`` logger carries exactly one ``NullHandler``."""
    handlers = logging.getLogger("lifx").handlers
    null_handlers = [h for h in handlers if type(h) is logging.NullHandler]
    assert len(null_handlers) == 1


def test_warning_without_app_configuration_is_silent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unconfigured application sees nothing on stderr from the library.

    Without the ``NullHandler`` the record would propagate to the root logger,
    find no handlers there, and be written by ``logging.lastResort``.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    for handler in saved_handlers:
        root.removeHandler(handler)
    try:
        logging.getLogger("lifx.network.connection").warning("unconfigured")
    finally:
        for handler in saved_handlers:
            root.addHandler(handler)

    assert capsys.readouterr().err == ""
