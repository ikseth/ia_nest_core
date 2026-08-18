from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ianest_core.config import load_config, validate_config_dict
from ianest_core.config.schema import TelemetryConfig
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import ConfigValidationError, ModelUnavailable, RoutingError
from ianest_core.evaluation import _task_adapters, run_eval
from ianest_core.registry import ModelRegistry, StaticAvailabilityProvider
from ianest_core.runtime import PromptRuntime
from ianest_core.telemetry.trace import ROTATE_SIZE_BYTES, TelemetryWriter
from ianest_core.identity import Identity


def test_domain_router_requires_semantic_router_config() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
    )

    with pytest.raises(RoutingError) as exc:
        router.route("tengo un error en el sistema")

    assert str(exc.value) == "routing requires config.router"


def test_prompt_runtime_uses_fallback_and_traces_substitution(tmp_path) -> None:
    config = _config_with_tmp_telemetry(tmp_path)
    runtime = PromptRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_a"}),
    )

    result = runtime.run(prompt="reporto un fallo", domain_id="support", request_id="fallback")

    assert result.model == "fake_b"
    assert result.trace["substituted"] is True
    assert result.trace["preferred_model"] == "fake_a"

    csv_text = (tmp_path / "trace.csv").read_text(encoding="utf-8")
    assert ";route;" in csv_text


def test_prompt_runtime_raises_model_unavailable_when_chain_is_down(tmp_path) -> None:
    config = _config_with_tmp_telemetry(tmp_path)
    runtime = PromptRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_a", "fake_b"}),
    )

    with pytest.raises(ModelUnavailable) as exc:
        runtime.run(prompt="reporto un fallo", domain_id="support")

    assert exc.value.type == "ModelUnavailable"
    assert exc.value.field == "model"


def test_config_validate_detects_dangling_reference() -> None:
    raw = {
        "models": [
            {
                "id": "only_model",
                "provider": "fake",
                "adapter": "openai_compatible",
                "endpoint": "fake://x",
                "model_name": "x",
                "capabilities": ["chat"],
                "profile": "default",
            }
        ],
        "domains": [
            {
                "id": "broken",
                "description": "Dominio con referencia colgante",
                "preferred_model": "does_not_exist",
                "fallback_models": [],
                "profile": "default",
                "status": "active",
            }
        ],
        "profiles": [{"id": "default", "temperature": 0.2}],
    }

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "preferred_model"


def test_eval_conformance_digest_is_stable() -> None:
    first = run_eval(track="conformance")
    second = run_eval(track="conformance")

    assert first["totals"]["conformance"] == {"pass": 121, "fail": 0}
    assert second["totals"]["conformance"] == {"pass": 121, "fail": 0}
    assert first["conformance_digest"] == second["conformance_digest"]
    assert first["conformance_digest"] == "fa9b79ffffb0034e366a93de14c5192b5e1946f4ef200f1c8356de078b90fc42"


def test_eval_v02_task_cases_still_pass() -> None:
    result = run_eval(battery_dir="eval/battery/v0.2", track="conformance")

    assert result["totals"]["conformance"] == {"pass": 12, "fail": 0}


def test_eval_v03_cases_pass() -> None:
    result = run_eval(battery_dir="eval/battery/v0.3", track="conformance")

    assert result["totals"]["conformance"] == {"pass": 50, "fail": 0}


def test_task_adapters_derivation_with_requirements_emits_json_object() -> None:
    adapters = _task_adapters(
        _task_case(
            {
                "derivations": [
                    {
                        "requirements": [{"id": "r1", "text": "resolver"}],
                        "subtasks": [{"prompt": "resuelve", "covers": ["r1"]}],
                    }
                ]
            }
        ),
        load_config("eval/fixtures/orchestration.yaml"),
    )

    assert json.loads(adapters["fake_planner"].responses[0]) == {
        "requirements": [{"id": "r1", "text": "resolver"}],
        "subtasks": [{"prompt": "resuelve", "covers": ["r1"]}],
    }


def test_task_adapters_derivation_without_requirements_emits_bare_list() -> None:
    subtasks = [{"prompt": "resuelve"}]
    adapters = _task_adapters(
        _task_case({"derivations": [{"subtasks": subtasks}]}),
        load_config("eval/fixtures/orchestration.yaml"),
    )

    assert json.loads(adapters["fake_planner"].responses[0]) == subtasks


def test_task_adapters_raw_derivation_emits_literal_text() -> None:
    adapters = _task_adapters(
        _task_case({"derivations": [{"raw": "esto no es JSON"}]}),
        load_config("eval/fixtures/orchestration.yaml"),
    )

    assert adapters["fake_planner"].responses == ["esto no es JSON"]


def test_task_adapters_derivations_precede_evaluation_decisions() -> None:
    first = {"subtasks": [{"prompt": "primera"}]}
    second = {"subtasks": [{"prompt": "segunda"}]}
    adapters = _task_adapters(
        _task_case(
            {
                "derivations": [first, second],
                "evaluate_decisions": ["rerun", "done"],
            }
        ),
        load_config("eval/fixtures/orchestration.yaml"),
    )

    assert adapters["fake_planner"].responses == [
        json.dumps(first["subtasks"], ensure_ascii=False),
        json.dumps(second["subtasks"], ensure_ascii=False),
        "rerun",
        "done",
    ]


def test_task_adapters_coverage_derivations_add_generator_and_validator() -> None:
    adapters = _task_adapters(
        _task_case(
            {
                "derivations": [{"units": [{"id": "u1", "description": "unidad"}]}],
                "generator_responses": {"fake_general": ["fragmento"]},
                "generator_finish_reasons": {"fake_general": ["length"]},
                "validator_decisions": [{"covered": ["u1"]}],
            },
            mode="coverage",
        ),
        load_config("eval/fixtures/orchestration_coverage.yaml"),
    )

    assert json.loads(adapters["fake_planner"].responses[0]) == [{"id": "u1", "description": "unidad"}]
    assert adapters["fake_general"].responses == ["fragmento"]
    assert adapters["fake_general"].finish_reasons == ["length"]
    assert json.loads(adapters["fake_validator"].responses[0]) == {"covered": ["u1"]}


def test_task_adapters_plans_keep_interleaved_decision_order() -> None:
    first = [{"prompt": "primera"}]
    second = [{"prompt": "segunda"}]
    adapters = _task_adapters(
        _task_case({"plans": [first, second], "evaluate_decisions": ["rerun", "done"]}),
        load_config("eval/fixtures/orchestration.yaml"),
    )

    responses = adapters["fake_planner"].responses
    assert responses[1] == "rerun"
    assert responses[3] == "done"
    assert [item["prompt"] for item in json.loads(responses[0])["subtasks"]] == ["primera"]
    assert [item["prompt"] for item in json.loads(responses[2])["subtasks"]] == ["segunda"]


def _task_case(script: dict[str, object], *, mode: str = "pipeline") -> dict[str, object]:
    return {"input": {"mode": mode}, "world": {"script": script}}


def test_telemetry_rotates_by_size(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    csv_path.write_text("x" * ROTATE_SIZE_BYTES, encoding="utf-8")
    writer = TelemetryWriter(
        TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(tmp_path / "trace.jsonl"), rotation="size")
    )

    writer.record(
        request_id="rotate",
        event="done",
        capability="prompt.run",
        identity=Identity(user_id="u1", service="local_cli"),
    )

    rotated = list(tmp_path.glob("trace.csv.*"))
    assert rotated
    assert csv_path.exists()


def _config_with_tmp_telemetry(tmp_path):
    return replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )
