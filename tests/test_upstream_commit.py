"""Tests for the upstream commit lookup used by the code generators."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

from lifx._upstream import UpstreamCommit, fetch_upstream_commit

COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def _response(payload: object) -> Mock:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    response.read = Mock(return_value=json.dumps(payload).encode())
    return response


class TestFetchUpstreamCommit:
    def test_success_returns_hash_and_commit_date(self) -> None:
        payload = [
            {
                "sha": COMMIT_SHA,
                "commit": {"committer": {"date": "2026-01-02T03:04:05Z"}},
            }
        ]
        with patch("lifx._upstream.urlopen", return_value=_response(payload)) as op:
            commit = fetch_upstream_commit("LIFX/products", "master", "products.json")

        assert commit == UpstreamCommit(COMMIT_SHA, "2026-01-02T03:04:05Z")
        url = op.call_args.args[0]
        assert url.startswith("https://api.github.com/repos/LIFX/products/commits?")
        assert "path=products.json" in url
        assert "sha=master" in url

    def test_network_failure_yields_unknown(self) -> None:
        with patch("lifx._upstream.urlopen", side_effect=OSError("offline")):
            commit = fetch_upstream_commit("LIFX/products", "master", "products.json")

        assert commit == UpstreamCommit("unknown", "unknown")

    def test_malformed_payload_yields_unknown(self) -> None:
        with patch("lifx._upstream.urlopen", return_value=_response([])):
            commit = fetch_upstream_commit("LIFX/products", "master", "products.json")

        assert commit == UpstreamCommit("unknown", "unknown")

    def test_invalid_json_yields_unknown(self) -> None:
        response = _response([])
        response.read = Mock(return_value=b"{ nope")
        with patch("lifx._upstream.urlopen", return_value=response):
            commit = fetch_upstream_commit("LIFX/products", "master", "products.json")

        assert commit == UpstreamCommit("unknown", "unknown")


class TestHeaderLines:
    def test_header_names_hash_and_timestamp(self) -> None:
        text = UpstreamCommit(COMMIT_SHA, "2026-01-02T03:04:05Z").header_lines()

        assert COMMIT_SHA in text
        assert "2026-01-02T03:04:05Z" in text
