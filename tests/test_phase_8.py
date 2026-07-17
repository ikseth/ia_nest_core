from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config
from ianest_core.config.schema import ProfileConfig, TelemetryConfig
from ianest_core.runtime import ReasoningRuntime


def test_reasoning_stops_on_model_done_and_emits_steps(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        responses=[
            {"output": "borrador", "done": False},
            {"output": "final", "done": True},
        ],
    )

    events = list(runtime.stream(prompt="resuelve", domain_id="general", request_id="reasoning-done"))
    result = runtime.run(prompt="resuelve", domain_id="general", request_id="reasoning-done-run")

    assert [event.type for event in events] == ["step", "step", "done"]
    assert [event.data["finish_reason"] for event in events[:-1]] == ["stop", "stop"]
    assert events[-1].data["stop_reason"] == "model_done"
    assert result.stop_reason == "model_done"
    assert result.output == "final"

    csv_text = (tmp_path / "trace.csv").read_text(encoding="utf-8")
    assert ";step;reasoning.run;" in csv_text
    assert ";done;reasoning.run;" in csv_text


def test_reasoning_stops_on_max_iterations(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        responses=[
            {"output": "i1", "done": False},
            {"output": "i2", "done": False},
        ],
        params={"max_iterations": 2},
    )

    result = runtime.run(prompt="resuelve", domain_id="general")

    assert result.stop_reason == "max_iterations"
    assert len(result.steps) == 2
    assert result.output == "i2"


def test_reasoning_stops_on_max_context_tokens(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        responses=[{"output": "borrador", "done": False}],
        params={"max_context_tokens": 1},
    )

    result = runtime.run(prompt="resuelve", domain_id="general")

    assert result.stop_reason == "max_context_tokens"
    assert len(result.steps) == 1


def test_reasoning_unparseable_done_falls_back_to_limit(tmp_path) -> None:
    runtime = _runtime(tmp_path, raw_responses=["sin json"], params={"max_iterations": 1})

    result = runtime.run(prompt="resuelve", domain_id="general")

    assert result.output == "sin json"
    assert result.stop_reason == "max_iterations"


def _runtime(
    tmp_path,
    responses: list[dict[str, object]] | None = None,
    raw_responses: list[str] | None = None,
    params: dict[str, object] | None = None,
) -> ReasoningRuntime:
    config = load_config(Path("eval/fixtures/config.yaml"))
    profile = config.profiles[0]
    profile_params = dict(profile.params)
    profile_params.update(params or {})
    config = replace(
        config,
        profiles=[ProfileConfig(id=profile.id, params=profile_params, extra=profile.extra)],
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )
    texts = raw_responses or [json.dumps(item) for item in responses or []]
    return ReasoningRuntime(config, adapter=ScriptedFakeAdapter("fake_b", texts))
