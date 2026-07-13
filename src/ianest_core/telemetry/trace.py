from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ianest_core.config.schema import TelemetryConfig
from ianest_core.errors import CoreError
from ianest_core.identity import Identity

SCHEMA_VERSION = "1"

TRACE_CSV_FIELDS = [
    "schema_version",
    "ts",
    "request_id",
    "event",
    "capability",
    "user_id",
    "service",
    "session_id",
    "domain_tag",
    "namespace",
    "domain",
    "model",
    "latency_ms",
    "tokens_in",
    "tokens_out",
    "verdict",
    "status",
    "error_type",
]


class TelemetryWriter:
    def __init__(self, config: TelemetryConfig | None) -> None:
        self.config = config
        self.errors: list[str] = []

    def record(
        self,
        *,
        request_id: str,
        event: str,
        capability: str,
        identity: Identity,
        payload: dict[str, Any] | None = None,
        domain: str = "",
        model: str = "",
        latency_ms: int | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        verdict: str = "",
        status: str = "ok",
        error_type: str = "",
        csv_event: bool = True,
        jsonl_event: bool = True,
    ) -> None:
        if self.config is None:
            return
        row = self._row(
            request_id=request_id,
            event=event,
            capability=capability,
            identity=identity,
            domain=domain,
            model=model,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            verdict=verdict,
            status=status,
            error_type=error_type,
        )
        json_event = {
            "schema_version": SCHEMA_VERSION,
            "ts": row["ts"],
            "request_id": request_id,
            "event": event,
            "capability": capability,
            **identity.to_dict(),
            "payload": payload or {},
        }
        self._best_effort(lambda: self._write(row, json_event, csv_event, jsonl_event))

    def _row(
        self,
        *,
        request_id: str,
        event: str,
        capability: str,
        identity: Identity,
        domain: str,
        model: str,
        latency_ms: int | None,
        tokens_in: int | None,
        tokens_out: int | None,
        verdict: str,
        status: str,
        error_type: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ts": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "event": event,
            "capability": capability,
            "user_id": identity.user_id,
            "service": identity.service,
            "session_id": identity.session_id,
            "domain_tag": identity.domain_tag,
            "namespace": identity.namespace,
            "domain": domain,
            "model": model,
            "latency_ms": "" if latency_ms is None else latency_ms,
            "tokens_in": "" if tokens_in is None else tokens_in,
            "tokens_out": "" if tokens_out is None else tokens_out,
            "verdict": verdict,
            "status": status,
            "error_type": error_type,
        }

    def _write(
        self,
        row: dict[str, Any],
        json_event: dict[str, Any],
        csv_event: bool,
        jsonl_event: bool,
    ) -> None:
        if self.config is None:
            return
        # TODO fase 6b: aplicar rotacion declarativa antes de escribir sinks.
        if csv_event and self.config.csv_path:
            csv_path = Path(self.config.csv_path)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
            with csv_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=TRACE_CSV_FIELDS, delimiter=";")
                if needs_header:
                    writer.writeheader()
                writer.writerow(row)
        if jsonl_event and self.config.jsonl_path:
            jsonl_path = Path(self.config.jsonl_path)
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(json_event, ensure_ascii=False, sort_keys=True) + "\n")

    def _best_effort(self, action: Any) -> None:
        try:
            action()
        except Exception as exc:
            self.errors.append(str(exc))
            if self.config is not None and self.config.strict_mode:
                raise CoreError("TelemetryError", str(exc), None) from exc
