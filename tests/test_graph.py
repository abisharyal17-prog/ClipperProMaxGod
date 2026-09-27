"""DAG engine: topological order, cache hits and cache invalidation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.graph import Graph, Node


class _ProducerParams(BaseModel):
    value: int = 1


class Producer(Node):
    type = "test_producer"
    title = "Producer"
    outputs = {"n": "Int"}
    params_model = _ProducerParams

    def __init__(self, node_id: str, params: dict[str, Any] | None = None, **kw: Any) -> None:
        super().__init__(node_id, params=params, **kw)
        self.calls = 0

    def run(self, ctx, inputs):  # noqa: ANN001 - test stub
        self.calls += 1
        return {"n": self.param("value")}


class Consumer(Node):
    type = "test_consumer"
    title = "Consumer"
    inputs = {"n": "Int"}
    outputs = {"m": "Int"}

    def __init__(self, node_id: str, **kw: Any) -> None:
        super().__init__(node_id, **kw)
        self.calls = 0

    def run(self, ctx, inputs):  # noqa: ANN001 - test stub
        self.calls += 1
        return {"m": int(inputs.get("n", 0)) + 1}


def _build() -> Graph:
    producer = Producer("p", {"value": 1})
    consumer = Consumer("c", wires={"n": {"node": "p", "port": "n"}})
    return Graph([producer, consumer], project_id="graph_test")


def test_order_is_topological():
    graph = _build()
    order = graph.order()
    assert order == ["p", "c"]
    assert order.index("p") < order.index("c")


def test_second_run_is_served_from_cache(ctx):
    graph = _build()
    graph.run(ctx)
    assert graph.nodes["p"].calls == 1
    assert graph.nodes["c"].calls == 1

    graph.run(ctx)
    assert graph.nodes["p"].calls == 1, "unchanged node should not re-run"
    assert graph.nodes["c"].calls == 1, "unchanged downstream node should not re-run"


def test_changing_a_param_busts_the_cache(ctx):
    graph = _build()
    graph.run(ctx)
    assert graph.nodes["p"].calls == 1

    graph.nodes["p"].params.value = 2
    graph.run(ctx)

    assert graph.nodes["p"].calls == 2, "param change must invalidate the node"
    assert graph.nodes["c"].calls == 2, "downstream must re-run when upstream changes"
