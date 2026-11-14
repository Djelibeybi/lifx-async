"""Check upstream file history and regenerate from an immutable revision.

The committed source marker is acknowledged only when its update PR is merged.
No cache, checkout of upstream code, or model invocation is needed.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

COMMITS_URL = (
    "https://api.github.com/repos/LIFX/products/commits"
    "?sha=master&path=products.json&per_page=1"
)


def validate_products(value: object, key: str = "") -> None:
    """Reject source-like strings in numeric catalogue fields before generation."""
    if isinstance(value, dict):
        for field, item in value.items():
            if not isinstance(field, str):
                raise ValueError("Catalogue keys must be strings")
            validate_products(item, field)
    elif isinstance(value, list):
        for item in value:
            validate_products(item, key)
    elif isinstance(value, str):
        if key != "name":
            raise ValueError(f"Unexpected string in catalogue field {key!r}")
    elif value is not None and type(value) not in (int, bool):
        raise ValueError(f"Unexpected value in catalogue field {key!r}")


def regenerate(products: dict | list, module_name: str, revision: dict) -> None:
    """Use the registry generator without rewriting curated hardware specs."""
    validate_products(products)
    generator = importlib.import_module(module_name)
    directory = Path(str(generator.__file__)).parent
    registry = directory / "registry.py"
    if module_name == "lifx.products.generator":
        upstream = generator.UpstreamCommit(
            sha=revision["sha"], date=revision["commit"]["committer"]["date"]
        )
        code = generator.generate_registry_file(products, upstream)
    else:
        code = generator.generate_registry_file(products)
    registry.write_text(code, encoding="utf-8")
    # specs.yml is curated hardware data, not part of the upstream catalogue.
    # The emulator generator rewrites it lossily, so never call that path here.
    for arguments in (["format"], ["check", "--fix"]):
        subprocess.run(
            [sys.executable, "-m", "ruff", *arguments, str(registry)], check=True
        )


def check(state_path: Path, module_name: str) -> None:
    """Acknowledge the upstream revision only after generation succeeds."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lifx-products-monitor",
    }
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    try:
        with urlopen(Request(COMMITS_URL, headers=headers), timeout=30) as response:
            commits = json.load(response)
            etag = response.headers.get("ETag")
    except HTTPError as error:
        if error.code != 304:
            raise
        error.close()
        print("Upstream products.json is unchanged.")
        return

    commit = commits[0]["sha"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid upstream commit SHA")
    if commit == state["commit"]:
        print("Upstream products.json is unchanged.")
        return

    # Never send the API token to raw.githubusercontent.com.
    url = f"https://raw.githubusercontent.com/LIFX/products/{commit}/products.json"
    with urlopen(url, timeout=30) as response:
        products = json.load(response)
    if not isinstance(products, (dict, list)):
        raise ValueError("Upstream product data must be an object or array")
    regenerate(products, module_name, commits[0])
    state_path.write_text(
        json.dumps({"commit": commit, "etag": etag}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Updated registry from LIFX/products@{commit}")


if __name__ == "__main__":
    check(Path(sys.argv[1]), sys.argv[2])
