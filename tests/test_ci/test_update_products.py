"""Offline regression tests for the upstream registry monitor."""

from __future__ import annotations

import importlib.util
import io
import json
from email.message import Message
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

pytestmark = pytest.mark.tooling

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "update_products.py"


@pytest.mark.parametrize("field", ["pid", "vid", "major", "minor", "temperature_range"])
def test_numeric_fields_reject_executable_strings(field):
    monitor = load_monitor()
    with pytest.raises(ValueError, match="Unexpected string"):
        monitor.validate_products([{field: "__import__('os').system('false')"}])


def load_monitor():
    spec = importlib.util.spec_from_file_location("update_products", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unchanged_response_does_not_generate_or_write(tmp_path, monkeypatch):
    monitor = load_monitor()
    state = tmp_path / "products-source.json"
    original = json.dumps({"commit": "a" * 40, "etag": '"baseline"'}) + "\n"
    state.write_text(original)
    error = HTTPError(monitor.COMMITS_URL, 304, "", Message(), io.BytesIO())
    request = Mock(side_effect=error)
    generate = Mock()
    monkeypatch.setattr(monitor, "urlopen", request)
    monkeypatch.setattr(monitor, "regenerate", generate)
    try:
        monitor.check(state, "unused")
    finally:
        error.close()
    assert state.read_text() == original
    assert request.call_count == 1
    assert request.call_args.args[0].get_header("If-none-match") == '"baseline"'
    generate.assert_not_called()


@pytest.mark.parametrize(
    "same_commit,fail_generation", [(True, False), (False, False), (False, True)]
)
def test_revision_handling(tmp_path, monkeypatch, same_commit, fail_generation):
    monitor = load_monitor()
    state = tmp_path / "state.json"
    old = "a" * 40
    new = old if same_commit else "b" * 40
    original = json.dumps({"commit": old, "etag": None})
    state.write_text(original)
    metadata = Mock()
    metadata.__enter__ = Mock(return_value=metadata)
    metadata.__exit__ = Mock(return_value=False)
    metadata.read = Mock(
        return_value=json.dumps(
            [{"sha": new, "commit": {"committer": {"date": "2026-11-05T00:00:00Z"}}}]
        ).encode()
    )
    metadata.headers = {"ETag": '"updated"'}
    catalogue = io.BytesIO(b'[{"vid": 1, "products": []}]')
    request = Mock(side_effect=[metadata, catalogue])
    generate = Mock(
        side_effect=RuntimeError("format failed") if fail_generation else None
    )
    monkeypatch.setattr(monitor, "urlopen", request)
    monkeypatch.setattr(monitor, "regenerate", generate)
    if fail_generation:
        with pytest.raises(RuntimeError, match="format failed"):
            monitor.check(state, "example.generator")
        assert state.read_text() == original
    else:
        monitor.check(state, "example.generator")
        if same_commit:
            assert state.read_text() == original
            generate.assert_not_called()
        else:
            assert json.loads(state.read_text()) == {"commit": new, "etag": '"updated"'}
            assert generate.call_args.args[:2] == (
                [{"vid": 1, "products": []}],
                "example.generator",
            )
            assert generate.call_args.args[2]["sha"] == new
    if not same_commit:
        assert request.call_args_list[1].args[0] == (
            f"https://raw.githubusercontent.com/LIFX/products/{new}/products.json"
        )


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_api_errors_are_not_acknowledged(tmp_path, monkeypatch, status):
    monitor = load_monitor()
    state = tmp_path / "state.json"
    state.write_text('{"commit": "baseline"}')
    error = HTTPError(monitor.COMMITS_URL, status, "", Message(), io.BytesIO())
    monkeypatch.setattr(monitor, "urlopen", Mock(side_effect=error))
    try:
        with pytest.raises(HTTPError):
            monitor.check(state, "unused")
    finally:
        error.close()
    assert json.loads(state.read_text()) == {"commit": "baseline"}


def test_real_generator_and_formatter(tmp_path, monkeypatch):
    monitor = load_monitor()
    directory = tmp_path / "products"
    directory.mkdir()
    generator = Mock()
    generator.__file__ = str(directory / "generator.py")
    generator.generate_registry_file.return_value = "PRODUCTS = {}\n"
    monkeypatch.setattr(
        monitor.importlib, "import_module", Mock(return_value=generator)
    )
    monitor.regenerate([], "example.generator", {"sha": "a" * 40})
    assert (directory / "registry.py").read_text() == "PRODUCTS = {}\n"
    generator.update_specs_file.assert_not_called()


def test_registry_preserves_pinned_provenance(tmp_path, monkeypatch):
    monitor = load_monitor()
    directory = tmp_path / "products"
    directory.mkdir()
    generator = Mock()
    generator.__file__ = str(directory / "generator.py")
    generator.generate_registry_file.return_value = "PRODUCTS = {}\n"
    monkeypatch.setattr(
        monitor.importlib, "import_module", Mock(return_value=generator)
    )
    revision = {
        "sha": "a" * 40,
        "commit": {"committer": {"date": "2026-11-05T00:00:00Z"}},
    }
    monitor.regenerate([], "lifx.products.generator", revision)
    generator.UpstreamCommit.assert_called_once_with(
        sha="a" * 40, date="2026-11-05T00:00:00Z"
    )
    generator.generate_registry_file.assert_called_once_with(
        [], generator.UpstreamCommit.return_value
    )
