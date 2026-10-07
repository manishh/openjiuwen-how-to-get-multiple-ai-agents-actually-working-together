"""smoke_test.py

Offline smoke tests for the SwarmFlow pipeline script, run through the
openJiuwen engine with its built-in MockBackend (no LLM / network needed).

Why there is no `from swarmflow import ...` here:
  `swarmflow` is not a package on disk. The engine installs the `swarmflow`
  facade into sys.modules only for the duration of a `run_workflow(...)` call
  (installed by `pip install workswarm`, which pulls in openjiuwen / Agent Core).
  The engine loads the pipeline script and resolves its `from swarmflow import ...`
  lines itself, so the tests drive the script through `run_workflow` instead.

Verifies that:
  1. The `swarmflow` operator facade resolves inside a running workflow.
  2. The pipeline script exposes a valid, literal META (read via AST, no import).
  3. The pipeline script defines an `async def run(args)`.
  4. The pipeline runs end-to-end on MockBackend and emits well-formed
     progress events.

Run with:  pytest tests/smoke_test.py -v
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

# The engine installs the `swarmflow` facade while run_workflow() executes.
from openjiuwen.agent_teams.workflow.engine import (
    MockBackend,
    ProgressKind,
    WorkflowProgressEvent,
    run_workflow,
)
from openjiuwen.agent_teams.workflow.engine.errors import MetaError
from openjiuwen.agent_teams.workflow.engine.loader import load_workflow_meta

# Path to the pipeline script under test (tests/ and src/ are siblings).
SCRIPT = Path(__file__).resolve().parent.parent / "src" / "swarmflow_pipeline.py"

# Launch args passed to run(args); the pipeline reads args.get("task").
SMOKE_ARGS = {"task": "Analyze market trends and draft a short strategy update."}


@pytest.fixture(scope="module")
def script_path() -> str:
    assert SCRIPT.is_file(), f"Pipeline script not found: {SCRIPT}"
    return str(SCRIPT)


@pytest.fixture(scope="module")
def meta(script_path: str) -> dict:
    """META extracted via AST only; the script is not imported."""
    return load_workflow_meta(script_path)


# ── 1.  SwarmFlow facade ─────────────────────────────────────────────────────


_PROBE_SCRIPT = '''
META = {"name": "probe", "description": "swarmflow facade probe", "phases": []}

async def run(args):
    import swarmflow  # resolved by the engine for the duration of the run
    names = ("agent", "parallel", "pipeline", "phase", "log")
    return {n: callable(getattr(swarmflow, n, None)) for n in names}
'''


def test_swarmflow_facade_resolves_during_run(tmp_path: Path) -> None:
    """Inside a running workflow, `swarmflow` exposes every required operator."""
    probe = tmp_path / "probe.py"
    probe.write_text(_PROBE_SCRIPT, encoding="utf-8")

    result = asyncio.run(run_workflow(str(probe), backend=MockBackend()))

    missing = [name for name, ok in result.items() if not ok]
    assert not missing, f"swarmflow is missing operators: {missing}"


# ── 2.  META ─────────────────────────────────────────────────────────────────


def test_meta_is_pure_literal(script_path: str) -> None:
    """META must be a pure literal so the engine can read it without importing."""
    try:
        load_workflow_meta(script_path)
    except MetaError as exc:  # pragma: no cover - failure path
        pytest.fail(f"META is not a valid pure-literal dict: {exc}")


def test_meta_is_dict(meta: dict) -> None:
    assert isinstance(meta, dict), "META must be a dict"


def test_meta_required_keys(meta: dict) -> None:
    """META must contain the keys the WorkSwarm runtime expects."""
    for key in ("name", "description", "version"):
        assert key in meta, f"META is missing required key: {key!r}"


def test_meta_name_nonempty(meta: dict) -> None:
    assert isinstance(meta["name"], str) and meta["name"].strip(), (
        "META['name'] must be a non-empty string"
    )


def test_meta_subtasks(meta: dict) -> None:
    """META['subtasks'] must be a non-empty list of dicts with 'role' keys."""
    subtasks = meta.get("subtasks", [])
    assert isinstance(subtasks, list) and len(subtasks) > 0, (
        "META['subtasks'] must be a non-empty list"
    )
    for st in subtasks:
        assert isinstance(st, dict) and "role" in st, (
            f"Each subtask must be a dict with a 'role' key; got {st!r}"
        )


# ── 3.  run() signature ──────────────────────────────────────────────────────


def test_run_is_async_function(script_path: str) -> None:
    """run() must be declared `async def` so the engine can await it.

    Checked statically (AST) so the script never has to be imported outside
    the engine.
    """
    tree = ast.parse(Path(script_path).read_text(encoding="utf-8"))
    top_level = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }
    assert "run" in top_level, "Pipeline script must define a top-level run()"
    assert isinstance(top_level["run"], ast.AsyncFunctionDef), (
        "run() must be declared `async def` so the engine can await it"
    )


# ── 4.  End-to-end on MockBackend ────────────────────────────────────────────


def test_pipeline_runs_on_mock_backend(script_path: str) -> None:
    """The pipeline completes offline and emits a well-formed event stream."""
    events: list[WorkflowProgressEvent] = []

    result = asyncio.run(
        run_workflow(
            script_path,
            backend=MockBackend(),
            args=SMOKE_ARGS,
            progress_sink=events.append,
        )
    )

    # The pipeline ran to completion and produced something.
    assert result is not None, "run() returned None on MockBackend"

    kinds = [e.kind for e in events]
    assert kinds, "No progress events were emitted"
    assert kinds[0] == ProgressKind.WORKFLOW_STARTED
    assert kinds[-1] == ProgressKind.WORKFLOW_COMPLETED
    assert ProgressKind.WORKFLOW_FAILED not in kinds

    # At least one agent call happened, and every start has a matching completion.
    started = [e for e in events if e.kind == ProgressKind.AGENT_STARTED]
    completed = [e for e in events if e.kind == ProgressKind.AGENT_COMPLETED]
    assert started, "Pipeline made no agent() calls"
    assert len(started) == len(completed), (
        f"{len(started)} agent calls started but {len(completed)} completed"
    )
    assert {e.agent_id for e in started} == {e.agent_id for e in completed}, (
        "AGENT_COMPLETED events do not match AGENT_STARTED events by agent_id"
    )


def test_pipeline_is_replayable_from_journal(script_path: str, tmp_path: Path) -> None:
    """A resumed run replays from the journal with zero fresh backend calls."""
    journal = str(tmp_path / "smoke.jsonl")

    asyncio.run(
        run_workflow(
            script_path,
            backend=MockBackend(),
            args=SMOKE_ARGS,
            journal_path=journal,
        )
    )

    class _NoCallBackend(MockBackend):
        calls = 0

        async def run(self, *a, **kw):  # type: ignore[override]
            type(self).calls += 1
            return await super().run(*a, **kw)

    asyncio.run(
        run_workflow(
            script_path,
            backend=_NoCallBackend(),
            args=SMOKE_ARGS,
            resume=journal,
        )
    )
    assert _NoCallBackend.calls == 0, "Resume should replay from the journal, not call the backend"