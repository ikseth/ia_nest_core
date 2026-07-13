from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

from ianest_core.adapters import FakeAdapter, ModelRequest, run_blocking
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.identity import Identity
from ianest_core.memory import NullMemoryAdapter
from ianest_core.runtime import PromptRuntime
from ianest_core.telemetry import TRACE_CSV_FIELDS, TelemetryWriter


def test_run_blocking_collects_fake_d2_flow() -> None:
    adapter = FakeAdapter(model="fake_a", response_text="hola mundo")
    req = ModelRequest(messages=[{"role": "user", "content": "hola"}])

    response = run_blocking(adapter, req)

    assert response.text == "hola mundo"
    assert response.model == "fake_a"
    assert response.tokens_in == 1
    assert response.tokens_out == 2


def test_prompt_runtime_propagates_identity_to_trace(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    jsonl_path = tmp_path / "trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(jsonl_path), strict_mode=False),
    )
    runtime = PromptRuntime(config)

    result = runtime.run(
        prompt="hola",
        domain_id="general",
        identity_override={"user_id": "u42", "service": "local_cli", "session_id": "s1"},
        request_id="req-test",
    )

    assert result.model == "fake_b"
    assert result.domain == "general"
    assert result.trace["request_id"] == "req-test"
    assert result.trace["user_id"] == "u42"
    assert result.trace["service"] == "local_cli"
    assert result.trace["session_id"] == "s1"
    assert result.trace["domain_tag"] == "general"
    assert result.trace["tokens_out"] > 0

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    assert rows
    assert list(rows[0].keys()) == TRACE_CSV_FIELDS
    done = [row for row in rows if row["event"] == "done"][0]
    assert done["user_id"] == "u42"
    assert done["service"] == "local_cli"
    assert done["session_id"] == "s1"
    assert done["domain_tag"] == "general"
    assert done["model"] == "fake_b"
    assert done["status"] == "ok"

    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    done_json = [event for event in events if event["event"] == "done"][0]
    assert done_json["payload"]["response"] == result.response
    assert done_json["user_id"] == "u42"


def test_null_memory_write_is_noop() -> None:
    adapter = NullMemoryAdapter()
    identity = Identity(user_id="u1", service="local_cli")

    assert adapter.read_context(identity, hints={"domain": "general"}) == {}
    assert adapter.write(identity, "short_term", {"text": "x"}) is None


def test_telemetry_non_serializable_payload_is_best_effort(tmp_path) -> None:
    writer = TelemetryWriter(
        TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
            strict_mode=False,
        )
    )

    writer.record(
        request_id="req",
        event="done",
        capability="prompt.run",
        identity=Identity(user_id="u1", service="local_cli"),
        payload={"bad": object()},
    )

    assert writer.errors
