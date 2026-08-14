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
    metavar: str | None


@dataclass(frozen=True)
class RestProjection:
    path: str
    method: str


@dataclass(frozen=True)
class CliProjection:
    group: str
    action: str | None
    description: str
    epilog: str | None = None
    flags: tuple[str, ...] = ()
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
    metavar: str | None = None,
) -> CapabilityParam:
    return CapabilityParam(name, type, required, choices, default, summary, metavar)


_PROMPT = _param(
    "prompt", "string", "texto que se enviara al modelo", required=True, metavar="TEXTO"
)
_DOMAIN = _param(
    "domain", "string", "dominio declarado usado para resolver el modelo", metavar="DOMINIO"
)
_MODEL = _param(
    "model", "string", "modelo directo; tiene prioridad sobre --domain", metavar="MODELO"
)
_TASK_PROMPT = _param(
    "prompt", "string", "tarea que se desea ejecutar", required=True, metavar="TEXTO"
)
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
        CliProjection(
            "capability",
            "list",
            "Lista capacidades, parametros y proyecciones de interfaz.",
            flags=("json",),
        ),
        McpProjection("capability.list"),
    ),
    Capability(
        "config.validate",
        "valida el archivo YAML",
        False,
        False,
        (),
        RestProjection("/config/validate", "POST"),
        CliProjection(
            "config",
            "validate",
            "Valida modelos, dominios, perfiles y referencias.",
            flags=("json",),
        ),
        McpProjection("config.validate"),
    ),
    Capability(
        "domain.list",
        "lista los dominios declarados",
        False,
        False,
        (),
        RestProjection("/domain/list", "GET"),
        CliProjection(
            "domain",
            "list",
            "Lista dominios, modelo preferido y estado.",
            flags=("json",),
        ),
        McpProjection("domain.list"),
    ),
    Capability(
        "domain.route",
        "propone dominio y modelo para un prompt",
        True,
        False,
        (
            _param(
                "prompt",
                "string",
                "texto que se desea enrutar",
                required=True,
                metavar="TEXTO",
            ),
        ),
        RestProjection("/domain/route", "POST"),
        CliProjection(
            "domain",
            "route",
            "Evalua las reglas declaradas y propone el dominio y modelo aplicables.",
            flags=("json",),
        ),
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
                metavar="DIRECTORIO",
            ),
        ),
        RestProjection("/eval/run", "POST"),
        CliProjection(
            "eval",
            "run",
            "Ejecuta los casos de la pista seleccionada.",
            flags=("json",),
        ),
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
                metavar="URL",
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
        CliProjection(
            "init",
            None,
            "Crea config/core.yaml y .env desde una plantilla y valida el resultado.",
        ),
        None,
    ),
    Capability(
        "model.list",
        "lista los modelos conocidos",
        False,
        False,
        (),
        RestProjection("/model/list", "GET"),
        CliProjection(
            "model",
            "list",
            "Lista modelos, proveedor, disponibilidad y perfil.",
            flags=("json",),
        ),
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
                metavar="MODELO",
            ),
        ),
        None,
        CliProjection(
            "model",
            "pull",
            "Descarga modelos ausentes mediante el provisioner compatible con su proveedor.",
            flags=("json",),
        ),
        None,
    ),
    Capability(
        "prompt.run",
        "ejecuta un prompt contra un modelo o dominio declarado",
        True,
        False,
        (_PROMPT, _DOMAIN, _MODEL),
        RestProjection("/prompt/run", "POST"),
        CliProjection(
            "prompt",
            "run",
            "Ejecuta un prompt contra un modelo local.",
            epilog=(
                "Resolucion: --model tiene prioridad sobre --domain. Sin ambos, usa "
                "el dominio por defecto; no enruta. Para enrutar por sentido, "
                "'ianest domain route' o 'ianest task run'."
            ),
            flags=("json", "quiet", "verbose"),
        ),
        McpProjection("prompt.run"),
    ),
    Capability(
        "prompt.stream",
        "emite los fragmentos del prompt mientras se ejecuta",
        True,
        True,
        (_PROMPT, _DOMAIN, _MODEL),
        RestProjection("/prompt/stream", "POST"),
        CliProjection(
            "prompt",
            "stream",
            "Ejecuta un prompt: la respuesta va a stdout y el progreso a stderr.",
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
        ),
        None,
    ),
    Capability(
        "reasoning.run",
        "ejecuta el razonamiento y devuelve el resultado final",
        True,
        False,
        (_PROMPT, _DOMAIN, _MODEL),
        RestProjection("/reasoning/run", "POST"),
        CliProjection(
            "reasoning",
            "run",
            "Ejecuta razonamiento iterativo y devuelve su salida final.",
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
        ),
        McpProjection("reasoning.run"),
    ),
    Capability(
        "reasoning.stream",
        "emite los eventos del razonamiento mientras se ejecuta",
        True,
        True,
        (_PROMPT, _DOMAIN, _MODEL),
        RestProjection("/reasoning/stream", "POST"),
        CliProjection(
            "reasoning",
            "stream",
            "Ejecuta razonamiento iterativo: la salida va a stdout y el progreso por paso a stderr.",
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
        ),
        None,
    ),
    Capability(
        "runtime.health",
        "detecta runtime, backend y GPU",
        False,
        False,
        (),
        RestProjection("/runtime/health", "GET"),
        CliProjection(
            "runtime",
            "health",
            "Informa de core, backend, modelos, GPU y version de protocolo MCP.",
            flags=("json",),
            aliases=("detect",),
        ),
        McpProjection("runtime.health"),
    ),
    Capability(
        "task.run",
        "ejecuta una tarea y muestra sus checkpoints",
        True,
        False,
        (_TASK_PROMPT, _MODE, _EFFORT),
        RestProjection("/task/run", "POST"),
        CliProjection(
            "task",
            "run",
            "Ejecuta task.run: la respuesta va a stdout y el progreso a stderr (--quiet lo silencia).",
            epilog=(
                "pipeline ejecuta el flujo multi-modelo de cinco etapas; coverage "
                "genera y valida unidades enumerables hasta completar su cobertura."
            ),
            flags=("json", "quiet", "verbose"),
        ),
        McpProjection("task.run"),
    ),
    Capability(
        "task.stream",
        "emite los eventos de una tarea mientras se ejecuta",
        True,
        True,
        (_TASK_PROMPT, _MODE, _EFFORT),
        RestProjection("/task/stream", "POST"),
        CliProjection(
            "task",
            "stream",
            "Ejecuta task.stream: emite cada evento como JSONL en stdout.",
            epilog=(
                "pipeline ejecuta el flujo multi-modelo de cinco etapas; coverage "
                "genera y valida unidades enumerables hasta completar su cobertura."
            ),
        ),
        None,
    ),
)

assert tuple(capability.name for capability in CAPABILITIES) == tuple(
    sorted(capability.name for capability in CAPABILITIES)
)
assert all(
    capability.cli is None
    or set(capability.cli.flags) <= {"json", "quiet", "verbose"}
    for capability in CAPABILITIES
)
