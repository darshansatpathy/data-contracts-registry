"""Command line: check, compat, release, validate, report, export, rules."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from datacontracts import __version__, compat, lineage, render, rules
from datacontracts.model import Registry, load_registry
from datacontracts.release import released, write_release
from datacontracts.validate import read_jsonl, validate_records


def _load(root: Path) -> Registry | None:
    reg, problems = load_registry(root)
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    return reg


def cmd_check(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    if reg is None:
        return 2
    findings = rules.run(reg, date.fromisoformat(a.today))
    if a.format == "markdown":
        print(render.findings_markdown(reg, findings, len(rules.REGISTRY)), end="")
    else:
        for f in findings:
            print(f"{f.severity.upper():8} {f.rule} {f.subject}: {f.message}")
        print(
            f"{len(reg.contracts)} contracts, {len(rules.REGISTRY)} rules: {len(findings)} findings"
        )
    threshold = rules.severity_rank(a.fail_on)
    return 1 if any(rules.severity_rank(f.severity) >= threshold for f in findings) else 0


def cmd_compat(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    if reg is None:
        return 2
    ids = [a.contract] if a.contract else sorted(reg.contracts)
    status = 0
    compared = 0
    for cid in ids:
        head = reg.contracts.get(cid)
        if head is None:
            print(f"error: no contract {cid}", file=sys.stderr)
            return 2
        rels, problems = released(reg.root, cid)
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
            status = 1
        prior = [r for r in rels if r.version != head.version]
        if not prior or len(prior) != len(rels):
            continue  # nothing to compare with, or this version is already released
        base = prior[-1].contract
        changes = compat.diff(base, head)
        if not changes:
            continue
        compared += 1
        needed = compat.required_bump(changes)
        impacts = lineage.impact(reg, head, [c for c in changes if c.level == "breaking"])
        print(render.compat_text(head, base.version, changes, needed, impacts), end="")
        for p in compat.version_problems(base, head, changes):
            print(f"  problem: {p}")
            status = 1
    if not compared:
        print("no contract differs from its last release")
    return status


def cmd_release(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    if reg is None:
        return 2
    ids = sorted(reg.contracts) if a.all else a.contracts
    if not ids:
        print("error: name contracts to release or pass --all", file=sys.stderr)
        return 2
    status = 0
    for cid in ids:
        c = reg.contracts.get(cid)
        if c is None:
            print(f"error: no contract {cid}", file=sys.stderr)
            return 2
        try:
            dest = write_release(reg.root, c)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            status = 1
            continue
        print(f"released {cid} {c.version} -> {dest.relative_to(reg.root)}")
    return status


def cmd_validate(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    if reg is None:
        return 2
    c = reg.contracts.get(a.contract)
    if c is None:
        print(f"error: no contract {a.contract}", file=sys.stderr)
        return 2
    path = Path(a.file)
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2
    rows, bad = read_jsonl(path)
    violations = [*bad, *validate_records(c, rows)]
    for v in violations[: a.max]:
        where = f"row {v.row}" + (f" {v.field}" if v.field else "")
        print(f"{where}: {v.rule}: {v.message}")
    if len(violations) > a.max:
        print(f"... and {len(violations) - a.max} more")
    print(f"{len(rows)} rows against {c.id} {c.version}: {len(violations)} violations")
    return 1 if violations else 0


def _sync(files: dict[str, str], root: Path, check: bool) -> int:
    stale = [
        rel
        for rel, text in files.items()
        if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != text
    ]
    if check:
        for rel in stale:
            print(f"stale: {rel}")
        if stale:
            print("run `dcr report` and `dcr export`, then commit the result")
            return 1
        print(f"{len(files)} generated files are current")
        return 0
    for rel in stale:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(files[rel], encoding="utf-8")
    print(f"wrote {len(stale)} of {len(files)} files")
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    return 2 if reg is None else _sync(render.all_reports(reg), reg.root, a.check)


def cmd_export(a: argparse.Namespace) -> int:
    reg = _load(Path(a.root))
    return 2 if reg is None else _sync(render.all_exports(reg), reg.root, a.check)


def cmd_rules(_: argparse.Namespace) -> int:
    for rid, sev, title, _why in rules.catalog():
        print(f"{rid}  {sev:8} {title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dcr", description="Data contracts as reviewed code.")
    p.add_argument("--version", action="version", version=f"dcr {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--root", default=".", help="registry directory (default: current)")

    c = sub.add_parser("check", help="run the policy rules")
    common(c)
    c.add_argument("--fail-on", choices=rules.SEVERITIES, default="high")
    c.add_argument("--format", choices=("text", "markdown"), default="text")
    c.add_argument("--today", default=date.today().isoformat(), help="ISO date for sunset checks")
    c.set_defaults(fn=cmd_check)

    k = sub.add_parser("compat", help="compare contracts with their last release")
    common(k)
    k.add_argument("--contract", help="one contract id")
    k.set_defaults(fn=cmd_compat)

    r = sub.add_parser("release", help="publish the current version of contracts")
    common(r)
    r.add_argument("contracts", nargs="*")
    r.add_argument("--all", action="store_true")
    r.set_defaults(fn=cmd_release)

    v = sub.add_parser("validate", help="check a JSON Lines file against a contract")
    common(v)
    v.add_argument("contract")
    v.add_argument("file")
    v.add_argument("--max", type=int, default=20, help="violations to print")
    v.set_defaults(fn=cmd_validate)

    for name, fn, helptext in (
        ("report", cmd_report, "write the markdown reports"),
        ("export", cmd_export, "write JSON Schema and DDL"),
    ):
        g = sub.add_parser(name, help=helptext)
        common(g)
        g.add_argument("--check", action="store_true", help="fail if the files are stale")
        g.set_defaults(fn=fn)

    sub.add_parser("rules", help="list the policy rules").set_defaults(fn=cmd_rules)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
