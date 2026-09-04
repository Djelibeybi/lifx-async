"""Structured contract audit for the complete Phase 11 mDNS surface."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import re
from pathlib import Path

import lifx
import lifx.network.discovery.mdns as mdns

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PUBLIC_PATHS = (
    Path("docs/api/devices.md"),
    Path("docs/api/network.md"),
    Path("docs/api/index.md"),
    Path("docs/user-guide/advanced-usage.md"),
    Path("docs/user-guide/discovery.md"),
    Path("examples/discovery_mdns.py"),
    Path("examples/discovery_progressive.py"),
)
# D-24 (Phase 14): CLAUDE.md is deliberately removed from this audit. It is
# reduced to a literal `@AGENTS.md` import plus only Claude-specific content,
# so the shared mDNS query-model prose this contract checks now lives in
# AGENTS.md alone (the canonical source) and is reachable from CLAUDE.md only
# through that import, not by duplication. See
# tests/test_repository_guidance.py for the import/no-duplication contract.
_REQUIRED_QUERY_MODEL_PATHS = (
    Path("AGENTS.md"),
    Path("docs/getting-started/quickstart.md"),
)
_QUERY_MODEL_PATHS = _REQUIRED_QUERY_MODEL_PATHS
# Task 2 (DOCS-05): the exact mDNS limitation phrases now live on the
# canonical discovery guide, not the advanced-usage summary that links to it.
_PUBLIC_GUIDANCE_PATH = Path("docs/user-guide/discovery.md")
_MIGRATION_GUIDANCE_PATH = Path("docs/migration/mdns-low-level-api-7.0.0.md")
_PRIVATE_GUIDANCE_PATH = Path("src/lifx/network/discovery/mdns/transport.py")
_MDNS_SOURCE_PATH = Path("src/lifx/network/discovery/mdns")

# Task 1 (DOCS-04): the canonical discovery guide and its single executable
# source. Kept as module-level constants so the drift-protection tests below
# and any future contract addition share one definition of "the guide" and
# "the example".
_DISCOVERY_GUIDE_PATH = Path("docs/user-guide/discovery.md")
_PROGRESSIVE_EXAMPLE_PATH = Path("examples/discovery_progressive.py")
_PROGRESSIVE_EXAMPLE_REGIONS = (
    "merged",
    "explicit-udp",
    "explicit-mdns",
    "targeted",
)
_PROGRESSIVE_EXAMPLE_FUNCTIONS = (
    "merged_discovery",
    "explicit_udp_discovery",
    "explicit_mdns_discovery",
    "targeted_lookup",
)


def _normalised_prose(relative_path: Path) -> str:
    """Return prose with headings and comments excluded from negative checks."""
    text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    prose_lines = (
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return " ".join(" ".join(prose_lines).split()).casefold()


def _count_prose_matches(relative_path: Path, pattern: str) -> int:
    """Count semantic matches only in normalised, non-comment prose."""
    return len(re.findall(pattern, _normalised_prose(relative_path)))


class TestPhase11SurfaceContract:
    """Prove the locked public, private, prose, and socket-code boundaries."""

    def test_raw_discovery_symbols_are_absent_from_package_surfaces(self) -> None:
        """Neither legacy raw names nor private replacements are re-exported."""
        forbidden_names = (
            "LifxServiceRecord",
            "discover_lifx_services",
            "TransportMethod",
            "_LifxServiceRecord",
            "_discover_lifx_services",
        )

        for package in (lifx, mdns):
            for name in forbidden_names:
                assert name not in package.__all__
                assert not hasattr(package, name)

    def test_record_to_device_factory_is_internal_with_its_record_type(self) -> None:
        """The raw-record cutover leaves no public factory with a private input."""
        assert "create_device_from_record" not in mdns.__all__
        assert not hasattr(mdns, "create_device_from_record")
        assert "_create_device_from_record" not in mdns.__all__
        assert not hasattr(mdns, "_create_device_from_record")

    def test_public_docs_and_example_exclude_private_contract_tokens(self) -> None:
        """Only the supported Device-level mDNS contract reaches public prose."""
        forbidden_tokens = (
            "LifxServiceRecord",
            "discover_lifx_services",
            "_LifxServiceRecord",
            "_discover_lifx_services",
            "TransportMethod",
        )

        for relative_path in _PUBLIC_PATHS:
            text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in text, f"{token} leaked into {relative_path}"
            assert re.search(r"(?<!\w)tm(?!\w)", text) is None
            assert re.search(r"\btransport[- ]method\b", text, re.IGNORECASE) is None

    def test_public_guidance_uses_the_approved_limitation_phrases(self) -> None:
        """The user guide states the exact supported legacy-unicast limits."""
        guidance = _normalised_prose(_PUBLIC_GUIDANCE_PATH)
        approved_phrases = (
            "ephemeral source port",
            "legacy-unicast replies",
            "does not join the multicast group",
            "does not receive unsolicited announcements",
            "does not authenticate or correlate responders",
            "mesh scale is proven synthetically",
            "A DNS AAAA record cannot carry that ID",
            "use `discover()` as the compatibility fallback",
            "schedules re-broadcasts 0.6, 1.8, 3.6, 5.6 and 7.6 seconds later",
            "they are not scaled to the requested discovery timeout",
            "a due re-broadcast is sent only while discovery remains active",
            "does not extend the overall timeout",
        )
        folded_guidance = guidance.casefold()

        for phrase in approved_phrases:
            assert phrase.casefold() in folded_guidance
        assert "only replies to its own queries" not in guidance

    def test_public_docs_make_no_mdns_speed_claims(self) -> None:
        """mDNS is an alternative discovery path, not a promised fast path."""
        speed_claim = re.compile(
            r"(?:mdns.{0,50}\b(?:faster|fastest)\b|"
            r"\b(?:faster|fastest)\b.{0,50}mdns)",
            re.IGNORECASE,
        )

        for relative_path in _PUBLIC_PATHS:
            assert speed_claim.search(_normalised_prose(relative_path)) is None

    def test_migration_guidance_covers_removed_low_level_api(self) -> None:
        """The intentional API break names every removal and its replacement."""
        guidance = (_REPO_ROOT / _MIGRATION_GUIDANCE_PATH).read_text(encoding="utf-8")
        removed_names = (
            "LifxServiceRecord",
            "discover_lifx_services",
            "create_device_from_record",
        )

        for name in removed_names:
            assert name in guidance
        assert "discover_mdns" in guidance

    def test_private_guidance_uses_the_approved_transport_phrases(self) -> None:
        """The private module states the complete implementation boundary."""
        guidance = (_REPO_ROOT / _PRIVATE_GUIDANCE_PATH).read_text(encoding="utf-8")
        approved_phrases = (
            "IPv4 multicast query",
            "ephemeral source port",
            "legacy-unicast replies",
            "does not join the multicast group",
            "does not receive unsolicited announcements",
            "does not authenticate or correlate responders",
            "cache-flush semantics do not apply",
            "cache state is scoped to one discovery call",
        )

        for phrase in approved_phrases:
            assert phrase in guidance

    def test_mdns_executable_ast_has_no_multicast_membership_or_rejoin(self) -> None:
        """Truthful no-membership docstrings are not mistaken for executable code."""
        forbidden_identifiers = {
            "IP_ADD_MEMBERSHIP",
            "IPV6_ADD_MEMBERSHIP",
            "IPV6_JOIN_GROUP",
            "join_multicast",
            "rejoin_multicast",
        }
        referenced_identifiers: set[str] = set()

        for source_path in sorted((_REPO_ROOT / _MDNS_SOURCE_PATH).glob("*.py")):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    referenced_identifiers.add(node.id)
                elif isinstance(node, ast.Attribute):
                    referenced_identifiers.add(node.attr)

        assert referenced_identifiers.isdisjoint(forbidden_identifiers)

    def test_query_model_contract_covers_repository_agent_and_quickstart_surfaces(
        self,
    ) -> None:
        """The query-model audit owns both agent guides and the quickstart."""
        assert set(_QUERY_MODEL_PATHS) == set(_REQUIRED_QUERY_MODEL_PATHS)

    def test_query_model_never_promises_a_single_total_query(self) -> None:
        """No audited prose may collapse the bounded model to one total query."""
        false_formulations = (
            r"\bsingle (?:total )?query\b",
            r"\bone total query\b",
            r"\bonly one query\b",
            r"\ba single datagram\b",
        )

        for relative_path in _QUERY_MODEL_PATHS:
            for pattern in false_formulations:
                assert _count_prose_matches(relative_path, pattern) == 0

    def test_query_model_documents_initial_ptr_and_both_retransmissions(
        self,
    ) -> None:
        """Each audited surface states the initial PTR and both retry times."""
        for relative_path in _QUERY_MODEL_PATHS:
            prose = _normalised_prose(relative_path)
            assert re.search(r"initial dns-sd ptr service query", prose)
            assert re.search(
                r"retransmit.{0,40}ptr query.{0,80}one second",
                prose,
            )
            assert re.search(
                r"retransmit.{0,40}ptr query.{0,140}three seconds",
                prose,
            )

    def test_query_model_documents_conditional_bounded_follow_ups(self) -> None:
        """Address follow-ups remain conditional and independently bounded."""
        for relative_path in _QUERY_MODEL_PATHS:
            prose = _normalised_prose(relative_path)
            assert re.search(r"valid srv target.{0,80}lacks a usable address", prose)
            assert re.search(r"bounded a/aaaa follow-ups", prose)
            assert re.search(
                r"one successful send.{0,100}no more than two failed attempts",
                prose,
            )
            assert re.search(r"(?:at most|no more than) 64 targets", prose)

    def test_corrected_surfaces_preserve_public_contract_boundaries(self) -> None:
        """Corrected prose does not widen the supported discovery contract."""
        forbidden_private_tokens = (
            "_LifxServiceRecord",
            "_discover_lifx_services",
        )
        unsupported_claims = (
            "listens for multicast announcements",
            "joins the multicast group to",
            "targets the packet address",
            "uses the packet address",
            "default discovery uses mdns",
            "discover() automatically uses mdns",
            "six broadcasts",
            "escalating schedule",
        )

        for relative_path in _QUERY_MODEL_PATHS:
            text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
            prose = _normalised_prose(relative_path)
            for token in forbidden_private_tokens:
                assert token not in text
            for claim in unsupported_claims:
                assert claim not in prose

            assert "async generator" in prose
            assert "explicit alternative" in prose
            assert "fall back" in prose or "fallback" in prose

        quickstart = _normalised_prose(Path("docs/getting-started/quickstart.md"))
        assert re.search(r'connectivity.{0,80}"wifi".{0,20}"thread"', quickstart)


class TestPhase14DiscoveryGuideContract:
    """DOCS-04: one executable example is the sole source of guide snippets."""

    def _load_progressive_example(self):
        """Import the example from its file path without executing `main()`."""
        module_path = _REPO_ROOT / _PROGRESSIVE_EXAMPLE_PATH
        spec = importlib.util.spec_from_file_location(
            "discovery_progressive_example", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_progressive_example_defines_every_migration_region(self) -> None:
        """Each guide snippet has a matching start/end region in the example."""
        source = (_REPO_ROOT / _PROGRESSIVE_EXAMPLE_PATH).read_text(encoding="utf-8")

        for region in _PROGRESSIVE_EXAMPLE_REGIONS:
            assert f"--8<-- [start:{region}]" in source, (
                f"missing start marker for {region!r}"
            )
            assert f"--8<-- [end:{region}]" in source, (
                f"missing end marker for {region!r}"
            )

    def test_progressive_example_imports_and_exposes_every_flow(self) -> None:
        """The example imports cleanly and defines all four migration flows."""
        module = self._load_progressive_example()

        for function_name in _PROGRESSIVE_EXAMPLE_FUNCTIONS:
            function = getattr(module, function_name, None)
            assert function is not None, f"missing {function_name}()"
            assert inspect.iscoroutinefunction(function)

    def test_discovery_guide_snippets_reference_the_progressive_example(
        self,
    ) -> None:
        """The guide includes every region from the one executable source,
        rather than hand-copying code that could drift from it."""
        guide = (_REPO_ROOT / _DISCOVERY_GUIDE_PATH).read_text(encoding="utf-8")

        for region in _PROGRESSIVE_EXAMPLE_REGIONS:
            assert f'"examples/discovery_progressive.py:{region}"' in guide, (
                f"guide does not include the {region!r} snippet"
            )

    def test_discovery_guide_covers_the_full_consumer_journey(self) -> None:
        """The guide names all three public discovery APIs and the required
        D-22 journey sections."""
        guide = (_REPO_ROOT / _DISCOVERY_GUIDE_PATH).read_text(encoding="utf-8")

        for api_name in ("discover(", "discover_udp(", "discover_mdns(", "find_by_ip("):
            assert api_name in guide

        journey_headings = (
            "unchanged",
            "explicit control",
            "targeted lookup and ipv6",
            "choosing a discovery method",
            "limitations",
            "troubleshooting",
        )
        folded_guide = guide.casefold()
        for heading in journey_headings:
            assert heading in folded_guide, f"missing journey section: {heading}"

    def test_discovery_surfaces_make_no_obsolete_default_mdns_claim(self) -> None:
        """The Phase 11 claim that default discovery is mDNS-only never
        returns to the canonical guide or its example."""
        unsupported_claims = (
            "default discovery uses mdns",
            "discover() automatically uses mdns",
            "only replies to its own queries",
        )

        for relative_path in (_DISCOVERY_GUIDE_PATH, _PROGRESSIVE_EXAMPLE_PATH):
            prose = _normalised_prose(relative_path)
            for claim in unsupported_claims:
                assert claim not in prose, f"{claim!r} present in {relative_path}"

    def test_discovery_surfaces_use_only_documentation_safe_addresses(self) -> None:
        """No raw/live identifier or private-infrastructure example reaches
        the canonical guide or its executable source."""
        private_ipv4_patterns = (
            r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
            r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
        )

        for relative_path in (_DISCOVERY_GUIDE_PATH, _PROGRESSIVE_EXAMPLE_PATH):
            text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
            for pattern in private_ipv4_patterns:
                assert not re.search(pattern, text), (
                    f"private-looking IPv4 literal found in {relative_path}"
                )


class TestPhase14DiscoveryLinkingContract:
    """DOCS-05/DOCS-06: the guide is linked and moved content is not
    duplicated across advanced-usage.md, the API reference and
    troubleshooting.md."""

    _ADVANCED_USAGE_PATH = Path("docs/user-guide/advanced-usage.md")
    _NETWORK_API_PATH = Path("docs/api/network.md")
    _TROUBLESHOOTING_PATH = Path("docs/user-guide/troubleshooting.md")
    _MOVED_MDNS_LIMITATION_PHRASES = (
        "does not join the multicast group",
        "does not receive unsolicited announcements",
        "mesh scale is proven synthetically",
    )
    _MOVED_UDP_SCHEDULE_PHRASE = (
        "schedules re-broadcasts 0.6, 1.8, 3.6, 5.6 and 7.6 seconds later"
    )

    def test_advanced_usage_links_to_the_discovery_guide_without_duplicating_it(
        self,
    ) -> None:
        """D-21: advanced-usage.md keeps a summary and link, not the moved
        substantive UDP/mDNS material."""
        text = (_REPO_ROOT / self._ADVANCED_USAGE_PATH).read_text(encoding="utf-8")
        prose = _normalised_prose(self._ADVANCED_USAGE_PATH)

        assert "discovery.md" in text
        for phrase in self._MOVED_MDNS_LIMITATION_PHRASES:
            assert phrase not in prose, (
                f"{phrase!r} still duplicated in {self._ADVANCED_USAGE_PATH}"
            )
        assert self._MOVED_UDP_SCHEDULE_PHRASE not in prose

    def test_network_api_page_links_to_the_discovery_guide_and_stays_concise(
        self,
    ) -> None:
        """The low-level API reference points at the consumer journey rather
        than re-narrating it."""
        text = (_REPO_ROOT / self._NETWORK_API_PATH).read_text(encoding="utf-8")
        assert "user-guide/discovery.md" in text

    def test_troubleshooting_gives_python_310_compatible_fan_out_advice(
        self,
    ) -> None:
        """DOCS-06 (troubleshooting scope): the 3.10-compatible replacement
        for the removed TaskGroup recommendation is present."""
        text = (_REPO_ROOT / self._TROUBLESHOOTING_PATH).read_text(encoding="utf-8")
        prose = _normalised_prose(self._TROUBLESHOOTING_PATH)

        assert "asyncio.create_task()" in text
        assert "python 3.10" in prose
        assert "unavailable" in prose
        assert "cancel" in prose

    def test_troubleshooting_never_recommends_taskgroup(self) -> None:
        """A bare `asyncio.TaskGroup` recommendation must not resurface."""
        prose = _normalised_prose(self._TROUBLESHOOTING_PATH)
        assert "with `asyncio.create_task()` or `asyncio.taskgroup`" not in prose
        assert "or asyncio.taskgroup` — no extra coordination" not in prose
