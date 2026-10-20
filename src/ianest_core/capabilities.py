from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ParamType = Literal["string", "integer", "boolean", "array", "object"]
CliInputSource = Literal["json_file"]


@dataclass(frozen=True)
class CapabilityParam:
    name: str
    type: ParamType
    required: bool
    choices: tuple[str, ...] | None
    default: object | None
    summary: str
    metavar: str | None
    cli: bool = True


@dataclass(frozen=True)
class RestProjection:
    path: str
    method: str


@dataclass(frozen=True)
class CliInput:
    name: str
    source: CliInputSource
    targets: tuple[str, ...]
    metavar: str
    summary: str


@dataclass(frozen=True)
class CliProjection:
    group: str
    action: str | None
    description: str
    presentation: dict[str, object]
    epilog: str | None = None
    flags: tuple[str, ...] = ()
    flag_help: tuple[tuple[str, str], ...] = ()
    aliases: tuple[str, ...] = ()
    alias_summaries: tuple[tuple[str, str], ...] = ()
    inputs: tuple[CliInput, ...] = ()
    order: int = 0


@dataclass(frozen=True)
class CliGroup:
    name: str
    summary: str
    description: str


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
    cli: bool = True,
) -> CapabilityParam:
    return CapabilityParam(name, type, required, choices, default, summary, metavar, cli)


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
_PLAN = _param(
    "plan",
    "array",
    "plan de subtareas suministrado; omite la etapa PLAN",
    cli=False,
)
_REQUIREMENTS = _param(
    "requirements",
    "array",
    "requisitos asociados al plan suministrado",
    cli=False,
)

_JSON_RESULT = ("json", "emite resultado")
_JSON_EVENTS = ("json", "emite cada evento como JSONL")
_JSON_CHECKPOINTS = ("json", "emite cada checkpoint como JSONL")
_JSON_CATALOG = ("json", "emite el catalogo completo")
_JSON_LISTING = ("json", "emite listado")
_JSON_EVAL = ("json", "emite resultado completo")
_JSON_REPORT = ("json", "emite informe")
_QUIET = ("quiet", "suprime el progreso en stderr; no afecta a la respuesta")
_VERBOSE = ("verbose", "enriquece el progreso en stderr; no afecta a la respuesta")


CLI_GROUPS: tuple[CliGroup, ...] = (
    CliGroup(
        "init",
        "crea la configuracion inicial y el archivo .env",
        "Crea config/core.yaml y .env desde una plantilla y valida el resultado.",
    ),
    CliGroup(
        "prompt",
        "ejecuta inferencias",
        "Ejecuta prompts mediante los modelos y dominios declarados.",
    ),
    CliGroup(
        "reasoning",
        "ejecuta razonamiento iterativo",
        "Ejecuta razonamiento controlado con los limites declarados en el perfil.",
    ),
    CliGroup(
        "task",
        "orquesta tareas multi-modelo",
        "Planifica, enruta, ejecuta, combina y evalua una tarea compleja.",
    ),
    CliGroup(
        "capability",
        "consulta las capacidades del core",
        "Consulta el catalogo publico de capacidades e interfaces.",
    ),
    CliGroup(
        "domain",
        "consulta y enruta dominios",
        "Consulta los dominios declarados o enruta un prompt.",
    ),
    CliGroup(
        "model",
        "consulta y aprovisiona modelos",
        "Consulta modelos o descarga los declarados que falten.",
    ),
    CliGroup(
        "config",
        "valida la configuracion",
        "Opera sobre la configuracion declarativa del core.",
    ),
    CliGroup(
        "eval",
        "ejecuta baterias de evaluacion",
        "Ejecuta evaluaciones de conformidad o smoke.",
    ),
    CliGroup(
        "runtime",
        "inspecciona runtime, backend y GPU",
        "Consulta salud y deteccion del entorno de ejecucion.",
    ),
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
            {"form": "table", "items": "capabilities", "columns": ("name", "summary")},
            flags=("json",),
            flag_help=(_JSON_CATALOG,),
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
            {"form": "opaque"},
            flags=("json",),
            flag_help=(_JSON_RESULT,),
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
            {
                "form": "table",
                "items": "domains",
                "columns": ("id", "preferred_model", "status"),
            },
            flags=("json",),
            flag_help=(_JSON_LISTING,),
            order=1,
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
            {"form": "row", "fields": ("domain", "model", "reason")},
            flags=("json",),
            flag_help=(_JSON_RESULT,),
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
            {"form": "row", "fields": ("verdict", "conformance_digest")},
            flags=("json",),
            flag_help=(_JSON_EVAL,),
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
            {"form": "opaque"},
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
            {
                "form": "table",
                "items": "models",
                "columns": ("id", "provider", "available", "profile"),
            },
            flags=("json",),
            flag_help=(_JSON_LISTING,),
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
            {"form": "opaque"},
            flags=("json",),
            flag_help=(_JSON_RESULT,),
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
            {"form": "text", "field": "response"},
            epilog=(
                "Resolucion: --model tiene prioridad sobre --domain. Sin ambos, usa "
                "el dominio por defecto; no enruta. Para enrutar por sentido, "
                "'ianest domain route' o 'ianest task run'."
            ),
            flags=("json", "quiet", "verbose"),
            flag_help=(_JSON_RESULT, _QUIET, _VERBOSE),
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
            {"form": "opaque"},
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
            flag_help=(_JSON_EVENTS, _QUIET, _VERBOSE),
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
            {"form": "text", "field": "output"},
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
            flag_help=(_JSON_RESULT, _QUIET, _VERBOSE),
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
            {"form": "opaque"},
            epilog="--model tiene prioridad sobre --domain; sin ambos, dominio por defecto (no enruta).",
            flags=("json", "quiet", "verbose"),
            flag_help=(_JSON_EVENTS, _QUIET, _VERBOSE),
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
            {"form": "opaque"},
            flags=("json",),
            flag_help=(_JSON_REPORT,),
            aliases=("detect",),
            alias_summaries=(("detect", "alias de health; detecta runtime, backend y GPU"),),
        ),
        McpProjection("runtime.health"),
    ),
    Capability(
        "task.plan",
        "deriva un plan ejecutable sin ejecutar subtareas",
        True,
        False,
        (_TASK_PROMPT, _EFFORT),
        RestProjection("/task/plan", "POST"),
        CliProjection(
            "task",
            "plan",
            "Deriva el plan de una tarea sin ejecutar subtareas.",
            {
                "form": "table",
                "items": "plan",
                "columns": ("index", "domain", "prompt"),
            },
            epilog=(
                "Con --json emite el objeto que task run acepta mediante "
                "--plan-file."
            ),
            flags=("json",),
            flag_help=(("json", "emite plan ejecutable completo"),),
        ),
        McpProjection("task.plan"),
    ),
    Capability(
        "task.run",
        "ejecuta una tarea y muestra sus checkpoints",
        True,
        False,
        (_TASK_PROMPT, _MODE, _PLAN, _REQUIREMENTS, _EFFORT),
        RestProjection("/task/run", "POST"),
        CliProjection(
            "task",
            "run",
            "Ejecuta task.run: la respuesta va a stdout y el progreso a stderr (--quiet lo silencia).",
            {"form": "text", "field": "response"},
            epilog=(
                "pipeline ejecuta el flujo multi-modelo de cinco etapas; coverage "
                "genera y valida unidades enumerables hasta completar su cobertura."
            ),
            flags=("json", "quiet", "verbose"),
            flag_help=(_JSON_CHECKPOINTS, _QUIET, _VERBOSE),
            inputs=(
                CliInput(
                    "plan-file",
                    "json_file",
                    ("plan", "requirements", "effort"),
                    "RUTA",
                    "JSON producido por task plan; rellena plan, requirements y effort",
                ),
            ),
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
            {"form": "opaque"},
            epilog=(
                "pipeline ejecuta el flujo multi-modelo de cinco etapas; coverage "
                "genera y valida unidades enumerables hasta completar su cobertura."
            ),
        ),
        None,
    ),
)

def _assert_catalog_invariants(capabilities: tuple[Capability, ...]) -> None:
    assert tuple(capability.name for capability in capabilities) == tuple(
        sorted(capability.name for capability in capabilities)
    )
    assert all(
        capability.cli is None
        or set(capability.cli.flags) <= {"json", "quiet", "verbose"}
        for capability in capabilities
    )
    assert all(
        parameter.cli
        or capability.cli is not None
        and any(parameter.name in input.targets for input in capability.cli.inputs)
        for capability in capabilities
        for parameter in capability.params
    )
    assert all(
        capability.cli is None
        or all(
            target in {parameter.name for parameter in capability.params}
            for input in capability.cli.inputs
            for target in input.targets
        )
        for capability in capabilities
    )
    assert {group.name for group in CLI_GROUPS} == {
        capability.cli.group for capability in capabilities if capability.cli is not None
    }
    assert all(
        capability.cli is None
        or set(dict(capability.cli.flag_help)) == set(capability.cli.flags)
        for capability in capabilities
    )
    assert all(
        capability.cli is None
        or set(dict(capability.cli.alias_summaries)) == set(capability.cli.aliases)
        for capability in capabilities
    )
    assert all(
        capability.cli is None or _valid_presentation(capability.cli.presentation)
        for capability in capabilities
    )
    assert all(
        not capability.streaming or capability.cli is None
        or capability.cli.presentation["form"] == "opaque"
        for capability in capabilities
    )


def _valid_presentation(presentation: object) -> bool:
    if not isinstance(presentation, dict):
        return False
    form = presentation.get("form")
    if form == "opaque":
        return set(presentation) == {"form"}
    if form == "text":
        return set(presentation) == {"form", "field"} and _field_name(
            presentation.get("field")
        )
    if form == "row":
        return set(presentation) == {"form", "fields"} and _field_names(
            presentation.get("fields")
        )
    if form == "table":
        return (
            set(presentation) == {"form", "items", "columns"}
            and _field_name(presentation.get("items"))
            and _field_names(presentation.get("columns"))
        )
    return False


def _field_name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _field_names(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and bool(value)
        and all(_field_name(item) for item in value)
        and len(set(value)) == len(value)
    )


_assert_catalog_invariants(CAPABILITIES)
