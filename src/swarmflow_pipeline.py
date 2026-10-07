"""swarmflow_pipeline.py

A WorkSwarm (formerly JiuwenSwarm) Cluster-mode SwarmFlow script that
orchestrates three specialist Teammate agents to complete a product-analysis
task for an e-commerce platform.

The mandatory top-level structure for every SwarmFlow script is:
  META  – static metadata dict read by the WorkSwarm runtime
  run() – async entry-point called by the engine

Operators come from the `swarmflow` package (installed via `pip install workswarm`).
Each `agent()` call takes a prompt plus keyword options (`label`, `schema`,
`options`).  `label` is display-only (it names the node in the /swarmflows
tree) and does not pick a model.  By default every worker inherits the teammate
model; to run a step on a different model pass `options={"model": "<alias>"}`.

See:
  SwarmFlow guide   https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/TUISwarmFlowGuide.md
  Agent Team guide  https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/AgentTeam.md
"""

from __future__ import annotations

# SwarmFlow operators are bundled with the `workswarm` pip package and
# exposed through the `swarmflow` namespace.
from swarmflow import agent, log, phase

import json

# ---------------------------------------------------------------------------
# META – required by the WorkSwarm runtime.  Keep it a plain dict literal.
# ---------------------------------------------------------------------------
META: dict = {
    # Human-readable identifier surfaced in the Web UI (http://localhost:5173)
    "name": "product-analysis-pipeline",
    # Shown on the Swarm task card
    "description": (
        "Three-stage product-analysis Swarm: market research → "
        "data summarization → executive report.  Demonstrates Cluster-mode "
        "Leader/Teammate coordination."
    ),
    "version": "1.0.0",
    # Subtask metadata used for documentation and the Web UI task-progress panel.
    # The engine reads the actual dependency graph from the pipeline
    # structure below, not from this list.
    "subtasks": [
        {
            "role": "market_researcher",
            "description": "Gather and structure market data",
            "success_criteria": "JSON with keys: trends, competitors, opportunities",
        },
        {
            "role": "data_summarizer",
            "description": "Distill the research into five actionable bullets",
            "success_criteria": "JSON with a 'bullets' list of exactly 5 strings",
        },
        {
            "role": "report_writer",
            "description": "Write the executive report from research and summary",
            "success_criteria": "JSON with Executive Summary, Key Findings, Recommendations",
        },
    ],
}


# ---------------------------------------------------------------------------
# JSON Schemas – `schema=` makes the engine return a parsed, validated object
# (this replaces the old free-text `success_criteria`).
# ---------------------------------------------------------------------------
RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "trends": {"type": "array", "items": {"type": "string"}},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "opportunities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["trends", "competitors", "opportunities"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
        }
    },
    "required": ["bullets"],
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["executive_summary", "key_findings", "recommendations"],
}


# ---------------------------------------------------------------------------
# run() – async entry-point.  The WorkSwarm engine calls this.
# ---------------------------------------------------------------------------
async def run(args: dict) -> dict:
    """Three chained Teammate agents: research -> summarize -> report.

    Args:
        args: Runtime arguments passed by the Leader / Web UI.  Recognizes:
              - task (str): high-level task description for the Swarm.

    Returns:
        A dict containing the report produced by the final Teammate.
    """
    task: str = args.get(
        "task",
        "Analyze current market trends for an e-commerce platform's top product category "
        "and produce a quarterly strategy update.",
    )

    # The three steps depend on each other, so they are plain sequential
    # awaits.  (pipeline() is for fanning a *list of items* through stages.)

    # ── Phase 1 ────────────────────────────────────────────────────────
    phase("Research")
    log("[Leader] Phase 1 - dispatching market_researcher Teammate")
    research = await agent(
        f"{task}\nReturn the trends, competitors and opportunities you find. Keep it short and return results quickly.",
        label="market_researcher",
        schema=RESEARCH_SCHEMA,
    )

    # ── Phase 2 ────────────────────────────────────────────────────────
    phase("Summarize")
    log("[Leader] Phase 2 - dispatching data_summarizer Teammate")
    summary = await agent(
        "Distill this market research into exactly 5 concise, actionable bullet points:\n"
        + json.dumps(research),
        label="data_summarizer",
        schema=SUMMARY_SCHEMA,
    )

    # ── Phase 3 ────────────────────────────────────────────────────────
    phase("Report")
    log("[Leader] Phase 3 - dispatching report_writer Teammate")
    report = await agent(
        "Write an executive report with sections 'Executive Summary', 'Key Findings' "
        "and 'Recommendations' from this research and summary:\n"
        + json.dumps({"research": research, "summary": summary}),
        label="report_writer",
        schema=REPORT_SCHEMA,
    )

    return {"report": report}


# ---------------------------------------------------------------------------
# Local validation: `swarmflow` only exists while the engine is running this
# script, so `python src/swarmflow_pipeline.py` cannot work.  Validate offline
# with:   pytest tests/smoke_test.py -v      (uses the engine's MockBackend)
# ---------------------------------------------------------------------------