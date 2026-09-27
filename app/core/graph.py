"""The node-graph engine.

A :class:`Node` is a unit of work with typed input/output ports. A :class:`Graph`
wires them together by port and executes them in dependency order, caching each
node's outputs. The same graph serializes to JSON, which is what the UI's node
canvas renders — so what you see *is* what runs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from app import __version__
from app.core.context import RunContext


class Node:
    """Base class for every pipeline stage."""

    type: ClassVar[str] = "node"
    title: ClassVar[str] = "Node"
    category: ClassVar[str] = "misc"
    description: ClassVar[str] = ""
    inputs: ClassVar[dict[str, str]] = {}
    outputs: ClassVar[dict[str, str]] = {}
    params_model: ClassVar[type[BaseModel] | None] = None

    def __init__(
        self,
        node_id: str,
        params: dict[str, Any] | None = None,
        wires: dict[str, dict[str, str]] | None = None,
        ui: dict[str, Any] | None = None,
    ) -> None:
        self.id = node_id
        self.params: Any = (
            self.params_model(**(params or {})) if self.params_model else (params or {})
        )
        self.wires = wires or {}
        self.ui = ui or {}

    # -- helpers ------------------------------------------------------------
    def param(self, name: str, default: Any = None) -> Any:
        if isinstance(self.params, BaseModel):
            return getattr(self.params, name, default)
        return self.params.get(name, default)

    def params_dict(self) -> dict[str, Any]:
        if isinstance(self.params, BaseModel):
            return self.params.model_dump()
        return dict(self.params)

    def fingerprint(self, upstream: dict[str, str]) -> str:
        payload = {
            "v": __version__,
            "type": self.type,
            "code": _source_hash(type(self)),
            "params": self.params_dict(),
            "upstream": upstream,
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:32]

    # -- work ---------------------------------------------------------------
    def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.type} id={self.id!r}>"


_SRC_HASH_CACHE: dict[type, str] = {}


def _source_hash(cls: type) -> str:
    """Hash a node class's source so code edits invalidate cached artifacts."""
    if cls not in _SRC_HASH_CACHE:
        try:
            import inspect

            src = inspect.getsource(cls)
            _SRC_HASH_CACHE[cls] = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
        except (OSError, TypeError):
            _SRC_HASH_CACHE[cls] = ""
    return _SRC_HASH_CACHE[cls]


def _outputs_valid(root: Path, value: Any) -> bool:
    """True when every project-local file referenced by *value* still exists."""
    root_str = str(root)
    if isinstance(value, str):
        if value.startswith(root_str):
            return Path(value).exists()
        return True
    if isinstance(value, dict):
        return all(_outputs_valid(root, v) for v in value.values())
    if isinstance(value, list):
        return all(_outputs_valid(root, v) for v in value)
    return True


class Graph:
    def __init__(self, nodes: Iterable[Node], project_id: str | None = None) -> None:
        self.nodes: dict[str, Node] = {n.id: n for n in nodes}
        self.project_id = project_id
        self._validate()

    def _validate(self) -> None:
        for node in self.nodes.values():
            for port, wire in node.wires.items():
                if port not in node.inputs:
                    raise ValueError(f"{node.id}: unknown input port {port!r}")
                src_id, src_port = wire.get("node"), wire.get("port")
                if src_id not in self.nodes:
                    raise ValueError(f"{node.id}.{port}: source node {src_id!r} not found")
                if src_port not in self.nodes[src_id].outputs:
                    raise ValueError(f"{node.id}.{port}: {src_id} has no output {src_port!r}")

    def order(self) -> list[str]:
        order: list[str] = []
        done: set[str] = set()

        def visit(nid: str, stack: set[str]) -> None:
            if nid in done:
                return
            if nid in stack:
                raise ValueError(f"cycle detected at {nid!r}")
            stack.add(nid)
            for wire in self.nodes[nid].wires.values():
                visit(wire["node"], stack)
            stack.discard(nid)
            done.add(nid)
            order.append(nid)

        for nid in self.nodes:
            visit(nid, set())
        return order

    def run(self, ctx: RunContext, targets: list[str] | None = None) -> dict[str, dict]:
        results: dict[str, dict] = {}
        keys: dict[str, str] = {}
        plan = self.order()
        ctx.event("graph_start", total=len(plan))
        for index, nid in enumerate(plan):
            node = self.nodes[nid]
            ctx.current_node = nid
            ctx.event("node_index", index=index, total=len(plan))

            upstream_keys: dict[str, str] = {}
            inputs: dict[str, Any] = {}
            for port, wire in node.wires.items():
                src_id, src_port = wire["node"], wire["port"]
                upstream_keys[port] = keys.get(src_id, "")
                inputs[port] = results.get(src_id, {}).get(src_port)

            key = node.fingerprint(upstream_keys)
            keys[nid] = key

            cached = ctx.cache.get(key)
            if cached is not None and _outputs_valid(ctx.project.root, cached):
                results[nid] = cached
                ctx.event("done", pct=1.0, message=f"{node.title} (cached)", cached=True)
                if targets and nid == _last(targets):
                    break
                continue

            ctx.event("start", pct=0.0, message=node.title)
            outputs = node.run(ctx, inputs) or {}
            if not isinstance(outputs, dict):
                raise TypeError(f"{nid}.run() must return a dict of output ports")
            ctx.cache.put(key, outputs)
            results[nid] = outputs
            ctx.event("done", pct=1.0, message=node.title)

            if targets and nid == _last(targets):
                break

        ctx.current_node = None
        ctx.event("graph_done")
        return results

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "category": n.category,
                    "params": n.params_dict(),
                    "inputs": n.inputs,
                    "outputs": n.outputs,
                    "ui": n.ui,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from": {"node": w["node"], "port": w["port"]},
                    "to": {"node": n.id, "port": port},
                }
                for n in self.nodes.values()
                for port, w in n.wires.items()
            ],
        }


def _last(targets: list[str]) -> str | None:
    return targets[-1] if targets else None
