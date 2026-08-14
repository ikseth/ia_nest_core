from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ParamType = Literal["string", "integer", "boolean", "array", "object"]


@dataclass(frozen=True)
class CapabilityParam:
    name: str
    type: ParamType
    required: bool
    choices: tuple[str, ...] | None
    default: object | None
    summary: str


@dataclass(frozen=True)
class RestProjection:
    path: str
    method: str


@dataclass(frozen=True)
class CliProjection:
    group: str
    action: str | None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class McpProjection:
    tool: str


@dataclass(frozen=True)
class Capability:
    name: str
    summary: str
    identity: bool
    streaming: bool
    params: tuple[CapabilityParam, ...]
    rest: RestProjection | None
    cli: CliProjection | None
    mcp: McpProjection | None


def _param(
    name: str,
    type: ParamType,
    summary: str,
    *,
    required: bool = False,
    choices: tuple[str, ...] | None = None,
    default: object | None = None,
) -> CapabilityParam:
    return CapabilityParam(name, type, required, choices, default, summary)


_PROMPT = _param("prompt", "string", "texto que se enviara al modelo", required=True)
_TASK_PROMPT = _param("prompt", "string", "tarea que se desea ejecutar", required=True)
_MODE = _param(
    "mode",
    "string",
    "modo de ejecucion de task.run (por defecto: pipeline)",
    choices=("pipeline", "coverage"),
    default="pipeline",
)
_EFFORT = _param(
    "effort",
    "string",
    "nivel de esfuerzo; sin bandera usa orchestration.default_effort",
    choices=("low", "medium", "high"),
)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "capability.list",
        "lista las capacidades publicas del core",
        False,
        False,
        (),
        RestProjection("/capability/list", "GET"),
        CliProjection("capability", "list"),
        McpProjection("capability.list"),
    ),
    Capability(
        "config.validate",
        "valida el archivo YAML",
        False,
        False,
        (),
        RestProjection("/config/validate", "POST"),
        CliProjection("config", "validate"),
        McpProjection("config.validate"),
    ),
    Capability(
        "domain.list",
        "lista los dominios declarados",
        False,
        False,
        (),
        RestProjection("/domain/list", "GET"),
        CliProjection("domain", "list"),
        McpProjection("domain.list"),
    ),
    Capability(
        "domain.route",
        "propone dominio y modelo para un prompt",
        True,
        False,
        (_param("prompt", "string", "texto que se desea enrutar", required=True),),
        RestProjection("/domain/route", "POST"),
        CliProjection("domain", "route"),
        McpProjection("domain.route"),
    ),
    Capability(
        "eval.run",
        "ejecuta una pista de evaluacion",
        False,
        False,
        (
            _param(
                "track",
                "string",
                "pista determinista o contra backend real (por defecto: conformance)",
                choices=("conformance", "smoke"),
                default="conformance",
            ),
            _param(
                "battery_dir",
                "string",
                "directorio de la bateria (por defecto: eval/battery)",
                default="eval/battery",
            ),
        ),
        RestProjection("/eval/run", "POST"),
        CliProjection("eval", "run"),
        McpProjection("eval.run"),
    ),
    Capability(
        "init",
        "crea la configuracion inicial y el archivo .env",
        False,
        False,
        (
            _param(
                "endpoint",
                "string",
                "endpoint OpenAI-compatible; si se omite se pregunta (por defecto: http://localhost:11434/v1)",
            ),
            _param(
                "template",
                "string",
                "plantilla de configuracion (por defecto: minimal)",
                choices=("lab", "minimal"),
                default="minimal",
            ),
            _param(
                "force",
                "boolean",
                "sobrescribe config/core.yaml y .env si ya existen",
                default=False,
            ),
        ),
        None,
        CliProjection("init", None),
        None,
    ),
    Capability(
        "model.list",
        "lista los modelos conocidos",
        False,
        False,
        (),
        RestProjection("/model/list", "GET"),
        CliProjection("model", "list"),
        McpProjection("model.list"),
    ),
    Capability(
        "model.pull",
        "descarga modelos mediante el provisioner del backend",
        False,
        False,
        (
            _param(
                "models",
                "array",
                "id o nombre de modelo; sin valores procesa todos los modelos declarados",
                default=(),
            ),
        ),
        None,
        CliProjection("model", "pull"),
        None,
    ),
    Capability(
        "prompt.run",
        "ejecuta un prompt contra un modelo o dominio declarado",
        True,
        False,
        (_PROMPT,),
        RestProjection("/prompt/run", "POST"),
        CliProjection("prompt", "run"),
        McpProjection("prompt.run"),
    ),
    Capability(
        "prompt.stream",
        "emite los fragmentos del prompt mientras se ejecuta",
        True,
        True,
        (_PROMPT,),
        RestProjection("/prompt/stream", "POST"),
        CliProjection("prompt", "stream"),
        None,
    ),
    Capability(
        "reasoning.run",
        "ejecuta el razonamiento y devuelve el resultado final",
        True,
        False,
        (_PROMPT,),
        RestProjection("/reasoning/run", "POST"),
        CliProjection("reasoning", "run"),
        McpProjection("reasoning.run"),
    ),
    Capability(
        "reasoning.stream",
        "emite los eventos del razonamiento mientras se ejecuta",
        True,
        True,
        (_PROMPT,),
        RestProjection("/reasoning/stream", "POST"),
        CliProjection("reasoning", "stream"),
        None,
    ),
    Capability(
        "runtime.health",
        "detecta runtime, backend y GPU",
        False,
        False,
        (),
        RestProjection("/runtime/health", "GET"),
        CliProjection("runtime", "health", ("detect",)),
        McpProjection("runtime.health"),
    ),
    Capability(
        "task.run",
        "ejecuta una tarea y muestra sus checkpoints",
        True,
        False,
        (_TASK_PROMPT, _MODE, _EFFORT),
        RestProjection("/task/run", "POST"),
        CliProjection("task", "run"),
        McpProjection("task.run"),
    ),
    Capability(
        "task.stream",
        "emite los eventos de una tarea mientras se ejecuta",
        True,
        True,
        (_TASK_PROMPT, _MODE, _EFFORT),
        RestProjection("/task/stream", "POST"),
        CliProjection("task", "stream"),
        None,
    ),
)

assert tuple(capability.name for capability in CAPABILITIES) == tuple(
    sorted(capability.name for capability in CAPABILITIES)
)
