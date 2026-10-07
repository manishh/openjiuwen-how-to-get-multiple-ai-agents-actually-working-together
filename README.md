# WorkSwarm Product-Analysis Pipeline

The pipeline runs three sequential phases. Each phase's output feeds the next prompt, and each `agent()` call uses a JSON `schema` so the engine returns validated, structured output.

1. **Research** (`market_researcher`): returns `trends`, `competitors` and `opportunities`.
2. **Summarize** (`data_summarizer`): distills the research into exactly five bullet points.
3. **Report** (`report_writer`): writes an executive report with `executive_summary`, `key_findings` and `recommendations`.

The script's return value is `{"report": {...}}`. Agent Core's ReliabilityRail watches the run and can correct a problem locally, escalate it to the Leader, or notify you.

## Prerequisites

- Python 3.11, 3.12, or 3.13
- API credentials for at least one supported LLM provider

## Installation

```bash
git clone https://github.com/draftdev/openjiuwen-how-to-get-multiple-ai-agents-actually-working-together
cd openjiuwen-how-to-get-multiple-ai-agents-actually-working-together
pip install -r requirements.txt
```

WorkSwarm is published on PyPI as [`workswarm`](https://pypi.org/project/workswarm/), and installing it also pulls in Agent Core (`openjiuwen`) and the SwarmFlow engine.

## Configuration

Copy the example config to the WorkSwarm config directory:

```bash
mkdir -p ~/.jiuwenswarm/config/
cp config/config.yaml ~/.jiuwenswarm/config/config.yaml
```

Each model entry under `models.defaults` has a `model_name`, an `api_base` (up to the version level only), an `api_key`, a `client_provider`, and an optional `alias`. The entry marked `is_default: true` is the fallback. The file reads its API keys from environment variables, so export them before you start the services:

```bash
export OPENAI_API_KEY=your-openai-key
export DEEPSEEK_API_KEY=your-deepseek-key
```

You can also configure credentials and model details through the Web UI at `http://localhost:5173` under **Settings > Models**.

## How to Run

Initialize and start WorkSwarm:

```bash
jiuwenswarm-init
jiuwenswarm-start
```

1. Open [`http://localhost:5173`](http://localhost:5173) and provide model details if prompted.
2. Choose **Cluster mode** in the chat box.
3. Load `src/swarmflow_pipeline.py` with the **+** button in the chat box.
4. Ask the Leader to start the Swarm, for example by entering `Start the swarm`.

The task-progress panel shows each phase and Teammate as it runs. You can also open the group chat, which shows the agents' messages to each other. When all three Teammates finish, the Leader reports back with a summary.

## Testing

The smoke tests run the pipeline **offline** through the openJiuwen engine's `MockBackend`, so they don't require API keys:

```bash
pytest -v tests/smoke_test.py
```

These tests verify that:

- the `swarmflow` operators resolve inside a running workflow
- `META` is a valid literal with the required keys and subtasks
- `run()` is `async`
- the pipeline completes end to end with a well-formed event stream (three agent calls, each start matched by a completion)
- a resumed run replays from the journal with no new backend calls

> **Note:** `swarmflow` is not a regular package. The engine installs it only while a workflow is running, so `import swarmflow` (or `python src/swarmflow_pipeline.py`) fails outside the engine. Always run the script through `run_workflow(...)`, as the tests do, or through WorkSwarm (using Web UI).


## File Reference

| File | Description |
|------|-------------|
| `src/swarmflow_pipeline.py` | The SwarmFlow script: a literal `META` dict and an async `run()` that awaits three `agent()` calls in sequence, with `phase()` and `log()` markers. |
| `config/config.yaml` | Example WorkSwarm config: a default `gpt-4o` entry and an optional `deepseek-chat` entry with the alias `light`. Copy to `~/.jiuwenswarm/config/config.yaml` before running. |
| `tests/smoke_test.py` | Offline smoke tests that drive the pipeline with `MockBackend`. |
| `Dockerfile.reviewer` | Docker image for reviewers to test the pipeline in an isolated environment. Requires relevant ports exposed on the host machine. |

## Supported Model Providers

WorkSwarm supports the following providers:

- OpenAI
- DeepSeek
- DashScope
- SiliconFlow
- InferenceAffinity
- OpenRouter
- Huawei Cloud MaaS
- Any OpenAI-compatible endpoint (set `client_provider` to `OpenAI` and supply the correct `api_base`)

To run one step on a different model, register it under an alias and pass `options={"model": "<alias>"}` on that `agent()` call. The `label=` on a call only names the step in the run tree; it doesn't pick a model.

## References

- [Agent Team guide](https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/AgentTeam.md)
- [SwarmFlow guide](https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/TUISwarmFlowGuide.md)
- [Configuration guide](https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/Configuration.md)
- [WorkSwarm on PyPI](https://pypi.org/project/workswarm/)

---