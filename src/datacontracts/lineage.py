"""Lineage between contracts and the consumers a change would reach."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from datacontracts.compat import Change
from datacontracts.model import Contract, Registry


def split_ref(ref: str) -> tuple[str, str] | None:
    """``sales.raw_orders.email`` becomes ``("sales.raw_orders", "email")``."""
    contract, sep, name = ref.rpartition(".")
    return (contract, name) if sep and contract and name else None


def downstream_map(reg: Registry) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {cid: [] for cid in reg.contracts}
    for c in reg.contracts.values():
        for up in c.upstream:
            if up in out:
                out[up].append(c.id)
    return {k: sorted(v) for k, v in out.items()}


def find_cycles(reg: Registry) -> list[list[str]]:
    """Each cycle once, as a list of contract ids that starts and ends on the same id."""
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for up in sorted(reg.contracts[node].upstream):
            if up not in reg.contracts:
                continue
            if state.get(up, 0) == 0:
                visit(up)
            elif state[up] == 1:
                cycles.append([*stack[stack.index(up) :], up])
        stack.pop()
        state[node] = 2

    for cid in sorted(reg.contracts):
        if state.get(cid, 0) == 0:
            visit(cid)
    return cycles


def downstream_closure(reg: Registry, cid: str) -> list[str]:
    """Every contract that depends on ``cid``, nearest first, without repeats."""
    dm = downstream_map(reg)
    seen: set[str] = {cid}
    order: list[str] = []
    queue: deque[str] = deque(dm.get(cid, []))
    while queue:
        nxt = queue.popleft()
        if nxt in seen:
            continue
        seen.add(nxt)
        order.append(nxt)
        queue.extend(dm.get(nxt, []))
    return order


def pii_leaks(reg: Registry) -> list[tuple[Contract, str, str]]:
    """Fields derived from a personal-data field that are neither marked pii nor masked."""
    out: list[tuple[Contract, str, str]] = []
    for c in reg.contracts.values():
        for f in c.fields:
            if f.derived_from is None or f.pii or f.masked:
                continue
            ref = split_ref(f.derived_from)
            src = reg.contracts.get(ref[0]) if ref else None
            srcf = src.field_named(ref[1]) if src and ref else None
            if srcf is not None and srcf.pii:
                out.append((c, f.name, f.derived_from))
    return out


@dataclass(frozen=True)
class Impact:
    contract: str
    consumer: str
    team: str
    criticality: str
    via: str


def _derived_from(d: Contract, source_id: str) -> dict[str, str]:
    """Fields of ``d`` that are derived from a field of ``source_id``, as {field: source field}."""
    out: dict[str, str] = {}
    for f in d.fields:
        ref = split_ref(f.derived_from) if f.derived_from else None
        if ref and ref[0] == source_id:
            out[f.name] = ref[1]
    return out


def impact(reg: Registry, head: Contract, changes: list[Change]) -> list[Impact]:
    """Consumers reached by the changes: direct readers, then readers of downstream contracts."""
    if not changes:
        return []
    whole = any(c.subject == "" for c in changes)
    fields = {c.subject for c in changes if c.subject}
    found: list[Impact] = []
    for cons in head.consumers:
        if whole or fields & set(cons.fields):
            found.append(Impact(head.id, cons.id, cons.team, cons.criticality, "direct"))
    for did in downstream_closure(reg, head.id):
        d = reg.contracts[did]
        derived = {
            name for name, src in _derived_from(d, head.id).items() if whole or src in fields
        }
        if not derived and not (whole and head.id in d.upstream):
            continue
        for cons in d.consumers:
            if whole or not derived or derived & set(cons.fields):
                found.append(Impact(did, cons.id, cons.team, cons.criticality, f"via {did}"))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(found, key=lambda i: (order[i.criticality], i.contract, i.consumer))
