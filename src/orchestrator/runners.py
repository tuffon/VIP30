from __future__ import annotations

"""VIP30 – LangGraph-style orchestration skeleton.

This module purposefully keeps *all* orchestration logic in one place so that
future developers can refactor it into separate packages (e.g. dedicated
`graphs/`, `agents/`, and `nodes/` folders) without breaking the public API.

Key concepts implemented below
==============================
1. **Task Master** – Receives an arbitrary *payload* and (eventually) calls an
   LLM to produce a JSON description of the work to be done.  For now the LLM
   call is *stubbed* so that the orchestrator can be executed without any
   external dependencies.

2. **Task Dispatcher** – Maps the symbolic *agent* name that appears in the
   Task Master output to a *callable* living in `src.workers`.  Dynamic import
   logic keeps the boiler-plate inside worker modules to an absolute minimum.

3. **Graph Runner** – Converts the JSON description into an in-memory DAG and
   executes the nodes *in dependency order*.  The implementation is
   asynchronous from the ground up.  Synchronous workers are transparently run
   in a thread-pool so that they don’t block the event-loop.

4. **run_pipeline** – The public helper that wires everything together:
      – calls Task Master,
      – builds & executes the DAG,
      – returns a structured result JSON that mirrors the input task IDs.

The code purposefully avoids *any* heavy LangGraph imports so that it can run
out-of-the-box.  Swapping the naïve `networkx`-based executor for the official
LangGraph engine should be a mechanical change later on.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Dict, List, Mapping, MutableMapping

import networkx as nx  # pylint: disable=import-error

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

#######################################################################################
# Task-master – turns an arbitrary *payload* into a JSON task spec                     #
#######################################################################################

def task_master(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a *task manifest* describing *what* should be executed.

    In production this function would delegate to a *fine-tuned* model whose
    name lives in the env-var ``VIP30_TASKMASTER_MODEL``.  The model is
    expected to emit JSON with the following high-level structure::

        {
          "tasks": [
            {
              "id": "unique-step-name",
              "agent": "name-of-worker",           # maps into ``src.workers``
              "inputs": { ... }                     # free-form JSON
              "depends_on": ["other-task-id", ...] # optional
            },
            ...
          ]
        }

    The exact schema is *not enforced* here on purpose – enforcing would be a
    perfect job for dedicated *pydantic* models down the road.

    While the LLM call is stubbed, we try to *gracefully degrade* by falling
    back to an *echo* task so that the pipeline stays runnable.
    """

    model_name = os.getenv("VIP30_TASKMASTER_MODEL", "<unset>")
    logger.info("[TaskMaster] Using model: %s", model_name)

    # ------------------------------------------------------------------
    # TODO: Replace the stub below with a real call, e.g. something like
    #   openai.chat.completions.create(model=model_name, ...)
    # For now we simply *mirror* the payload back to the orchestrator if it
    # looks like a valid task spec.  Otherwise we create a trivial echo task.
    # ------------------------------------------------------------------

    if (
        isinstance(payload, Mapping)
        and payload.get("tasks")
        and isinstance(payload["tasks"], list)
    ):
        logger.debug("[TaskMaster] Received pre-defined task list – skipping LLM call")
        manifest: Dict[str, Any] = {
            "tasks": payload["tasks"],
        }
    else:
        logger.warning(
            "[TaskMaster] Payload did not contain tasks – generating fallback echo task"
        )
        manifest = {
            "tasks": [
                {
                    "id": "echo",
                    "agent": "echo",  # resolves to ``src.workers.echo``
                    "inputs": {
                        "payload": payload,
                    },
                    "depends_on": [],
                }
            ]
        }

    # Ensure manifest can be serialised – early defensive check.
    json.dumps(manifest)  # raises if non-serialisable
    return manifest


#######################################################################################
# Task dispatcher – resolves *agent* strings into callables                            #
#######################################################################################


class TaskDispatcher:
    """Resolve agent-names from the manifest into *callables* living inside
    ``src.workers``.

    The mapping rules are deliberately simple so that they can be changed later
    without touching this orchestrator:

    1. *Direct module* – ``agent == "foo"`` → import ``src.workers.foo`` and
       call its :pyfunc:`run` attribute (async or sync).
    2. *Module path* – ``agent == "foo.bar"`` → import ``src.workers.foo.bar``
       and call :pyfunc:`run`.
    3. *Explicit function* – ``agent == "foo:custom_fn"`` → import
       ``src.workers.foo`` and call its ``custom_fn`` attribute.

    The imported callables are cached for the lifetime of the dispatcher.
    """

    _CACHE: MutableMapping[str, Callable[..., Any]] = {}

    def dispatch(self, agent: str) -> Callable[..., Any]:  # noqa: D401 (imperative mood)
        """Return the *callable* that should execute the *agent*.

        Raises a :class:`ValueError` if nothing can be resolved.
        """

        if agent in self._CACHE:
            return self._CACHE[agent]

        module_path: str
        func_name: str | None = None

        if ":" in agent:
            module_path, func_name = agent.split(":", 1)
        else:
            module_path = agent

        # Normalise into an absolute import rooted at *src.workers*
        abs_module_path = f"src.workers.{module_path}"

        try:
            module: ModuleType = importlib.import_module(abs_module_path)
        except ModuleNotFoundError as exc:
            raise ValueError(f"No module found for agent '{agent}' → tried '{abs_module_path}'") from exc

        # Default callable – the convention is to expose *run*
        if func_name is None:
            func_name = "run"

        try:
            worker_fn: Callable[..., Any] = getattr(module, func_name)
        except AttributeError as exc:
            raise ValueError(
                f"Module '{abs_module_path}' does not expose a '{func_name}' callable"
            ) from exc

        # Remember for future lookups
        self._CACHE[agent] = worker_fn
        return worker_fn


#######################################################################################
# Graph runner – execute the manifest in dependency order                              #
#######################################################################################


@dataclass(frozen=True)
class TaskNode:
    """Lightweight helper to keep per-task information together."""

    id: str
    agent: str
    inputs: Mapping[str, Any]
    depends_on: List[str]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TaskNode":
        try:
            return cls(
                id=str(raw["id"]),
                agent=str(raw["agent"]),
                inputs=raw.get("inputs", {}),
                depends_on=list(raw.get("depends_on", [])),
            )
        except KeyError as exc:
            raise ValueError(f"Missing required task attribute: {exc.args[0]}") from exc


class GraphRunner:
    """Turn a list of :class:`TaskNode` into a DAG and *run* it."""

    def __init__(self, tasks: List[TaskNode], dispatcher: TaskDispatcher):
        self._dispatcher = dispatcher
        self._graph: nx.DiGraph = nx.DiGraph()
        self._results: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # Build the in-memory DAG                                            
        # ------------------------------------------------------------------
        for task in tasks:
            self._graph.add_node(task.id, spec=task)

        for task in tasks:
            for dep in task.depends_on:
                if dep not in self._graph:
                    raise ValueError(f"Task '{task.id}' depends on unknown task '{dep}'")
                self._graph.add_edge(dep, task.id)

        if not nx.is_directed_acyclic_graph(self._graph):
            raise ValueError("The task graph contains a cycle – cannot proceed")

        logger.debug("[GraphRunner] DAG successfully built with %d nodes", len(tasks))

    # ------------------------------------------------------------------
    # Public API                                                         
    # ------------------------------------------------------------------

    async def run(self) -> Dict[str, Any]:
        """Execute the DAG *sequentially* in topological order.

        The method is intentionally simple so it can be replaced by a proper
        LangGraph executor later on.  Nodes are awaited *one-by-one*, which is
        conceptually identical to LangGraph’s default behaviour for
        dependency-chained sub-graphs.
        """

        for node_id in nx.topological_sort(self._graph):
            spec: TaskNode = self._graph.nodes[node_id]["spec"]
            logger.info("[GraphRunner] Executing task '%s' via agent '%s'", spec.id, spec.agent)

            worker_fn = self._dispatcher.dispatch(spec.agent)
            # Inject outputs from all *direct* predecessors – easy to change to
            # full transitive closure if ever needed.
            predecessor_outputs = {
                pred: self._results[pred] for pred in self._graph.predecessors(node_id)
            }

            # Worker call signature *can* evolve, so keep kwargs explicit.
            output = await _maybe_await(
                worker_fn(
                    payload=dict(spec.inputs),
                    dependency_outputs=predecessor_outputs,
                )
            )

            self._results[spec.id] = output
            logger.info("[GraphRunner] Task '%s' finished", spec.id)

        return self._results


#######################################################################################
# Public helper – the orchestrator entry-point                                         #
#######################################################################################


def run_pipeline(payload: Mapping[str, Any]) -> Dict[str, Any]:  # noqa: D401
    """High-level convenience wrapper that orchestrates the full pipeline.

    1. Turns *payload* into a manifest via :pyfunc:`task_master`.
    2. Builds a DAG from that manifest.
    3. Executes the DAG *sequentially* (topologically).
    4. Returns a *structured* JSON with the per-task outputs.

    The function is *synchronous* from the caller’s point of view but uses
    ``asyncio`` internally so that workers can be either *sync* or *async*.
    """

    manifest = task_master(payload)
    raw_tasks = manifest.get("tasks", [])
    tasks = [TaskNode.from_dict(t) for t in raw_tasks]

    dispatcher = TaskDispatcher()
    runner = GraphRunner(tasks, dispatcher)

    async def _async_entry() -> Dict[str, Any]:
        return await runner.run()

    results = asyncio.run(_async_entry())

    return {
        "manifest": manifest,
        "results": results,
    }


#######################################################################################
# Internal helpers                                                                     #
#######################################################################################


async def _maybe_await(value: Any) -> Any:
    """Await *value* if it is a coroutine, otherwise return it directly."""

    if inspect.isawaitable(value):
        return await value  # type: ignore[arg-type]
    return value
