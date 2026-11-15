"""Released versions of contracts.

A release is a copy of the contract at a version, stored under ``releases/<id>/<version>.toml``,
with the hash of its parsed content recorded in ``releases/index.json``. Released content is
immutable: changing it means publishing a new version.
"""

from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from datacontracts.compat import parse_semver
from datacontracts.model import Contract, canonical_hash, parse_contract


@dataclass(frozen=True)
class Released:
    version: str
    contract: Contract
    hash: str


def read_index(root: Path) -> dict[str, dict[str, str]]:
    path = root / "releases" / "index.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {cid: dict(v) for cid, v in data.items()}


def _write_index(root: Path, index: dict[str, dict[str, str]]) -> None:
    path = root / "releases" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def released(root: Path, cid: str) -> tuple[list[Released], list[str]]:
    """Released versions of ``cid``, oldest first, and any integrity problems found."""
    problems: list[str] = []
    out: list[Released] = []
    for version, recorded in read_index(root).get(cid, {}).items():
        rel = f"releases/{cid}/{version}.toml"
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: recorded in the index but the file is missing")
            continue
        try:
            with path.open("rb") as fh:
                raw = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            problems.append(f"{rel}: invalid TOML: {exc}")
            continue
        contract = parse_contract(raw, rel)
        if contract is None:
            problems.append(f"{rel}: does not parse as a contract")
            continue
        actual = canonical_hash(raw)
        if actual != recorded:
            problems.append(
                f"{rel}: content hash {actual[:12]} does not match the index ({recorded[:12]})"
            )
            continue
        if contract.version != version or contract.id != cid:
            problems.append(f"{rel}: file says {contract.id} {contract.version}")
            continue
        out.append(Released(version, contract, actual))
    out.sort(key=lambda r: parse_semver(r.version) or (0, 0, 0))
    return out, problems


def write_release(root: Path, contract: Contract) -> Path:
    """Publish the contract at its current version. Refuses to overwrite a different release."""
    index = read_index(root)
    existing = index.get(contract.id, {}).get(contract.version)
    new_hash = canonical_hash(contract.raw)
    if existing is not None and existing != new_hash:
        raise ValueError(
            f"{contract.id} {contract.version} is already released with different content; "
            "bump the version"
        )
    dest = root / "releases" / contract.id / f"{contract.version}.toml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / contract.source, dest)
    index.setdefault(contract.id, {})[contract.version] = new_hash
    _write_index(root, index)
    return dest
