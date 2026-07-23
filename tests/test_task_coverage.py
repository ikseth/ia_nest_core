from __future__ import annotations

import json
import time
from dataclasses import replace
from threading import Lock

import pytest

from ianest_core.adapters import Event, ScriptedFakeAdapter
from ianest_core.errors import AdapterError, CoreError
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.runtime import TaskRuntime
from ianest_core.runtime.task_runtime import _CoverageUnit, _parse_covered_ids


class CapturingAdapter(ScriptedFakeAdapter):
    def __init__(self, model: str, responses: list[str], finish_reasons: list[str] | None = None) -> None:
        super().__init__(model, responses)
        self.prompts: list[str] = []
        self.finish_reasons = finish_reasons or []
        self.calls = 0

    def stream(self, req):
        prompt = req.messages[-1]["content"]
        self.prompts.append(prompt)
        text = self._next_response()
        finish_reason = (
            self.finish_reasons[self.calls]
            if self.calls < len(self.finish_reasons)
            else self.finish_reason
        )
        self.calls += 1
        yield Event("token", {"text": text})
        yield Event(
            "done",
            {
                "text": text,
                "model": self.model,
                "tokens_in": len(prompt.split()),
                "tokens_out": len(text.split()),
                "finish_reason": finish_reason,
            },
        )


class FailOnceAdapter(CapturingAdapter):
    def stream(self, req):
        self.prompts.append(req.messages[-1]["content"])
        self.calls += 1
        if self.calls == 1:
            raise AdapterError("transient generator error")
        text = self._next_response()
        yield Event("token", {"text": text})
        yield Event(
            "done",
            {
                "text": text,
                "model": self.model,
                "tokens_in": 1,
                "tokens_out": 1,
                "finish_reason": "stop",
            },
        )


class ParallelState:
    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0
        self.lock = Lock()


class ParallelAdapter(CapturingAdapter):
    def __init__(self, model: str, response: str, state: ParallelState) -> None:
        super().__init__(model, [response])
        self.state = state

    def stream(self, req):
        with self.state.lock:
            self.state.active += 1
            self.state.maximum = max(self.state.maximum, self.state.active)
        time.sleep(0.03)
        try:
            yield from super().stream(req)
        finally:
            with self.state.lock:
                self.state.active -= 1


def test_coverage_ten_units_three_per_chunk(tmp_path) -> None:
    units = [{"id": f"u{index:02}", "prompt": f"punto {index}"} for index in range(1, 11)]
    decisions = [
        ["u01", "u02", "u03"],
        ["u04", "u05", "u06"],
        ["u07", "u08", "u09"],
        ["u10"],
    ]
    result = _runtime(tmp_path, units, ["A", "B", "C", "D"], decisions).run(
        prompt="cubre diez puntos",
        mode="coverage",
    )

    assert result.stop_reason == "task_done"
    assert result.response == "ABCD"
    assert result.coverage["completed_units"] == [unit["id"] for unit in units]
    assert result.coverage["failed_units"] == []
    assert result.coverage["pending_units"] == []
    assert result.coverage["chunk_index"] == 4


def test_coverage_next_generation_contains_only_pending_units(tmp_path) -> None:
    units = [{"id": f"u{index}", "prompt": f"detail-{index}"} for index in range(1, 5)]
    generator = CapturingAdapter("fake_general", ["ACCEPTED-TEXT", "LAST"])
    runtime = _runtime(
        tmp_path,
        units,
        [],
        [["u1", "u2", "u3"], ["u4"]],
        generator=generator,
    )

    result = runtime.run(prompt="objetivo", mode="coverage")

    assert result.response == "ACCEPTED-TEXTLAST"
    assert "detail-4" in generator.prompts[1]
    assert all(f"detail-{index}" not in generator.prompts[1] for index in range(1, 4))
    assert "ACCEPTED-TEXT" not in generator.prompts[1]


def test_coverage_generation_prompt_is_only_assigned_content() -> None:
    runtime = object.__new__(TaskRuntime)
    units = [_CoverageUnit(id="u1", prompt="solo el primer punto", depends_on=[])]

    prompt = runtime._coverage_generation_prompt(
        "responde diez puntos",
        units,
        ["u0"],
    )
    normalized = prompt.lower()

    assert "context only; do not answer it as a whole" in normalized
    assert "the only content to produce" in normalized
    assert "do not include a preamble, conclusion" in normalized
    assert "do not address unassigned units" in normalized
    assert "responde diez puntos" in prompt
    assert "solo el primer punto" in prompt


def test_coverage_adapter_error_retries_only_affected_unit(tmp_path) -> None:
    units = [
        {"id": "code", "prompt": "codigo", "domain_hint": "codigo"},
        {"id": "reason", "prompt": "razona", "domain_hint": "razonamiento"},
        {"id": "general", "prompt": "explica", "domain_hint": "general"},
    ]
    code = FailOnceAdapter("fake_code", ["CODE"])
    reason = CapturingAdapter("fake_reason", ["REASON"])
    general = CapturingAdapter("fake_general", ["GENERAL"])
    validator = CapturingAdapter(
        "fake_validator",
        [json.dumps(["reason"]), json.dumps(["general"]), json.dumps(["code"])],
    )
    runtime = _runtime(
        tmp_path,
        units,
        [],
        [],
        adapters={
            "fake_code": code,
            "fake_reason": reason,
            "fake_general": general,
            "fake_validator": validator,
        },
    )

    result = runtime.run(prompt="objetivo", mode="coverage")

    assert result.stop_reason == "task_done"
    assert result.response == "CODEREASONGENERAL"
    assert (code.calls, reason.calls, general.calls) == (2, 1, 1)
    assert result.coverage["retries"]["code"] == 1


def test_coverage_independent_groups_respect_max_parallel(tmp_path) -> None:
    state = ParallelState()
    units = [
        {"id": "code", "prompt": "codigo", "domain_hint": "codigo"},
        {"id": "reason", "prompt": "razona", "domain_hint": "razonamiento"},
        {"id": "general", "prompt": "explica", "domain_hint": "general"},
    ]
    runtime = _runtime(
        tmp_path,
        units,
        [],
        [],
        adapters={
            "fake_code": ParallelAdapter("fake_code", "CODE", state),
            "fake_reason": ParallelAdapter("fake_reason", "REASON", state),
            "fake_general": ParallelAdapter("fake_general", "GENERAL", state),
            "fake_validator": CapturingAdapter(
                "fake_validator",
                [json.dumps(["code"]), json.dumps(["reason"]), json.dumps(["general"])],
            ),
        },
    )

    result = runtime.run(prompt="objetivo", mode="coverage")

    assert result.stop_reason == "task_done"
    assert state.maximum == 2


def test_coverage_out_of_order_acceptance_retains_answer_prefix(tmp_path) -> None:
    units = [
        {"id": "u1", "prompt": "primero"},
        {"id": "u2", "prompt": "segundo"},
        {"id": "u3", "prompt": "tercero"},
    ]
    runtime = _runtime(
        tmp_path,
        units,
        ["THIRD", "FIRST", "SECOND"],
        [["u3"], ["u1"], ["u2"]],
    )

    events = list(runtime.stream(prompt="objetivo", mode="coverage"))
    result = next(event.data for event in reversed(events) if event.type == "task_done")
    answer_chunks = [event.data for event in events if event.type == "answer_chunk"]

    assert result["response"] == "FIRSTSECONDTHIRD"
    assert [chunk["text"] for chunk in answer_chunks] == ["FIRST", "SECOND", "THIRD"]
    assert [chunk["chunk_index"] for chunk in answer_chunks] == [2, 3, 1]


def test_coverage_dependencies_execute_in_plan_order(tmp_path) -> None:
    units = [
        {"id": "u1", "prompt": "base"},
        {"id": "u2", "prompt": "derived", "depends_on": ["u1"]},
        {"id": "u3", "prompt": "final", "depends_on": ["u2"]},
    ]
    generator = CapturingAdapter("fake_general", ["ONE", "TWO", "THREE"])
    result = _runtime(
        tmp_path,
        units,
        [],
        [["u1"], ["u2"], ["u3"]],
        generator=generator,
    ).run(prompt="objetivo", mode="coverage")

    assert result.response == "ONETWOTHREE"
    assert result.coverage["chunk_index"] == 3
    assert '"u1"' in generator.prompts[0]
    assert '"u2"' in generator.prompts[1]
    assert '"u3"' in generator.prompts[2]


def test_coverage_no_progress_preserves_partial_at_chunk_three(tmp_path) -> None:
    units = [
        {"id": "u1", "prompt": "posible"},
        {"id": "u2", "prompt": "imposible"},
    ]
    result = _runtime(
        tmp_path,
        units,
        ["ONE", "RETRY_ONE", "RETRY_TWO"],
        [["u1"], [], []],
    ).run(prompt="objetivo", mode="coverage")

    assert result.stop_reason == "no_progress"
    assert result.response == "ONE"
    assert result.coverage["completed_units"] == ["u1"]
    assert result.coverage["failed_units"] == ["u2"]
    assert result.coverage["pending_units"] == []
    assert result.coverage["chunk_index"] == 3


@pytest.mark.parametrize(
    ("simulated", "expected_reason"),
    [
        ({"elapsed_s": 31}, "max_time"),
        ({"context_tokens": 16385}, "max_total_tokens"),
    ],
)
def test_coverage_cuts_before_first_cycle(tmp_path, simulated, expected_reason) -> None:
    runtime = _runtime(
        tmp_path,
        [{"id": "u1", "prompt": "punto"}],
        ["ONE"],
        [],
        simulated=simulated,
    )

    result = runtime.run(prompt="objetivo", mode="coverage")

    assert result.stop_reason == expected_reason
    assert result.response == ""
    assert result.coverage["completed_units"] == []
    assert result.coverage["pending_units"] == ["u1"]
    assert result.coverage["chunk_index"] == 0


def test_coverage_max_chunks_does_not_exceed_eight(tmp_path) -> None:
    units = [{"id": f"u{index}", "prompt": f"punto {index}"} for index in range(1, 11)]
    result = _runtime(
        tmp_path,
        units,
        list("ABCDEFGH"),
        [[f"u{index}"] for index in range(1, 9)],
    ).run(prompt="objetivo", mode="coverage")

    assert result.stop_reason == "max_chunks"
    assert result.response == "ABCDEFGH"
    assert result.coverage["completed_units"] == [f"u{index}" for index in range(1, 9)]
    assert result.coverage["failed_units"] == []
    assert result.coverage["pending_units"] == ["u9", "u10"]
    assert result.coverage["chunk_index"] == 8


def test_coverage_run_and_stream_produce_same_result(tmp_path) -> None:
    units = [{"id": "u1", "prompt": "uno"}, {"id": "u2", "prompt": "dos"}]
    blocking = _runtime(tmp_path / "run", units, ["ONE"], [["u1", "u2"]]).run(
        prompt="objetivo",
        mode="coverage",
    )
    events = list(
        _runtime(tmp_path / "stream", units, ["ONE"], [["u1", "u2"]]).stream(
            prompt="objetivo",
            mode="coverage",
        )
    )
    streamed = next(event.data for event in reversed(events) if event.type == "task_done")

    assert streamed["response"] == blocking.response
    assert streamed["coverage"] == blocking.coverage


def test_coverage_jsonl_reconstructs_units_chunks_and_models(tmp_path) -> None:
    units = [
        {"id": "code", "prompt": "codigo", "domain_hint": "codigo"},
        {"id": "general", "prompt": "explica", "domain_hint": "general"},
    ]
    runtime = _runtime(
        tmp_path,
        units,
        [],
        [],
        adapters={
            "fake_code": CapturingAdapter("fake_code", ["CODE"]),
            "fake_general": CapturingAdapter("fake_general", ["GENERAL"]),
            "fake_validator": CapturingAdapter(
                "fake_validator",
                [json.dumps(["code"]), json.dumps(["general"])],
            ),
        },
    )

    result = runtime.run(prompt="objetivo", mode="coverage", request_id="parent")
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    done = next(event for event in reversed(events) if event["event"] == "task_done")
    unit_models = {
        event["payload"]["unit_id"]: event["payload"]["model"]
        for event in events
        if event["event"] == "subtask_done"
    }

    assert done["payload"]["coverage"]["completed_units"] == ["code", "general"]
    assert done["payload"]["chunks"] == result.chunks
    assert unit_models == {"code": "fake_code", "general": "fake_general"}


def test_coverage_rejects_invalid_mode_and_missing_config(tmp_path) -> None:
    with pytest.raises(CoreError) as invalid:
        _runtime(tmp_path, [{"id": "u1", "prompt": "uno"}], ["ONE"], [["u1"]]).run(
            prompt="objetivo",
            mode="invalid",
        )
    assert (invalid.value.type, invalid.value.field) == ("ConfigError", "mode")

    runtime = TaskRuntime(load_config("eval/fixtures/orchestration.yaml"))
    with pytest.raises(CoreError) as missing:
        runtime.run(prompt="objetivo", mode="coverage")
    assert (missing.value.type, missing.value.field) == (
        "ConfigError",
        "orchestration.coverage",
    )


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ('["u1", "u2"]', {"u1", "u2"}),
        ('```json\n["u1"]\n```', {"u1"}),
        ('{"covered": ["u1", "u2"]}', {"u1", "u2"}),
        ('{"decada_1920": [{"nombre_original": "Nosferatu"}], "decada_1930": []}', {"decada_1920", "decada_1930"}),
        ('[{"id": "u1"}, {"unit_id": "u2"}]', {"u1", "u2"}),
        ('no cubre nada util', set()),
        ('[]', set()),
    ],
)
def test_parse_covered_ids_tolerates_validator_formats(response, expected) -> None:
    assert _parse_covered_ids(response) == expected


def test_coverage_validator_prompt_requests_ids_only(tmp_path) -> None:
    units = [{"id": "d1920", "prompt": "cine de 1920"}]
    validator = CapturingAdapter("fake_validator", [json.dumps(["d1920"])])
    runtime = _runtime(tmp_path, units, ["FRAG"], [], adapters={"fake_validator": validator})

    runtime.run(prompt="obras maestras", mode="coverage")

    prompt = validator.prompts[0]
    assert "d1920" in prompt
    assert "only a json array" in prompt.lower()


def test_coverage_accepts_validator_dict_keyed_by_id(tmp_path) -> None:
    units = [{"id": "d1920", "prompt": "cine de 1920"}, {"id": "d1930", "prompt": "cine de 1930"}]
    validator_dict = json.dumps({"d1920": [{"film": "Nosferatu"}], "d1930": [{"film": "M"}]})
    runtime = _runtime(
        tmp_path,
        units,
        ["FRAG1", "FRAG2"],
        [],
        adapters={"fake_validator": CapturingAdapter("fake_validator", [validator_dict, validator_dict])},
    )

    result = runtime.run(prompt="obras maestras por decada", mode="coverage")

    assert result.stop_reason == "task_done"
    assert result.coverage["coverage_complete"] is True
    assert result.coverage["completed_units"] == ["d1920", "d1930"]


def test_coverage_plan_accepts_integer_and_missing_ids(tmp_path) -> None:
    units = [
        {"id": 1, "prompt": "uno"},
        {"prompt": "dos", "depends_on": [1]},
    ]
    result = _runtime(tmp_path, units, ["ONE", "TWO"], [["1"], ["u2"]]).run(
        prompt="tolerancia de ids",
        mode="coverage",
    )

    assert result.stop_reason == "task_done"
    assert result.response == "ONETWO"
    assert result.coverage["completed_units"] == ["1", "u2"]


def test_coverage_plan_rejects_duplicate_ids_after_coercion(tmp_path) -> None:
    units = [{"id": 1, "prompt": "uno"}, {"id": "1", "prompt": "repetido"}]

    with pytest.raises(CoreError) as exc:
        _runtime(tmp_path, units, ["ONE"], [["1"]]).run(prompt="duplicados", mode="coverage")

    assert exc.value.type == "PlanParseError"
    assert exc.value.field == "id"


def _runtime(
    tmp_path,
    units,
    responses,
    decisions,
    *,
    generator=None,
    adapters=None,
    simulated=None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = replace(
        load_config("eval/fixtures/orchestration_coverage.yaml"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )
    configured = {
        "fake_planner": CapturingAdapter("fake_planner", [json.dumps(units)]),
        "fake_general": generator or CapturingAdapter("fake_general", responses),
        "fake_validator": CapturingAdapter(
            "fake_validator",
            [json.dumps(decision) for decision in decisions],
        ),
    }
    configured.update(adapters or {})
    return TaskRuntime(
        config,
        adapter_factory=configured.get,
        simulated=simulated,
    )
