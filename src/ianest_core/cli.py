from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ianest_core.errors import CoreError
from ianest_core import service
from ianest_core.dotenv import load_dotenv

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
TEMPLATE_FILES = {
    "minimal": "core.example.yaml",
    "lab": "core.lab.example.yaml",
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    load_dotenv()
    try:
        if args.command == "init":
            return _init(args)
        if args.command == "prompt" and args.prompt_command == "run":
            return _prompt_run(args)
        if args.command == "reasoning" and args.reasoning_command == "run":
            return _reasoning_run(args)
        if args.command == "reasoning" and args.reasoning_command == "stream":
            return _reasoning_stream(args)
        if args.command == "task" and args.task_command == "run":
            return _task_run(args)
        if args.command == "domain" and args.domain_command == "route":
            return _domain_route(args)
        if args.command == "domain" and args.domain_command == "list":
            return _domain_list(args)
        if args.command == "model" and args.model_command == "list":
            return _model_list(args)
        if args.command == "model" and args.model_command == "pull":
            return _model_pull(args)
        if args.command == "config" and args.config_command == "validate":
            return _config_validate(args)
        if args.command == "eval" and args.eval_command == "run":
            return _eval_run(args)
        if args.command == "runtime" and args.runtime_command == "health":
            return _runtime_health(args)
        if args.command == "runtime" and args.runtime_command == "detect":
            return _runtime_detect(args)
    except CoreError as exc:
        return _emit_error(exc, json_output=getattr(args, "json", False))
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ianest",
        description="Orquesta modelos locales, dominios, razonamiento y evaluacion.",
        epilog=(
            "Usa 'ianest GRUPO --help' para ver sus acciones y "
            "'ianest GRUPO ACCION --help' para ver todas sus opciones."
        ),
    )
    parser.add_argument(
        "--config",
        default="config/core.yaml",
        metavar="RUTA",
        help="ruta de configuracion YAML (por defecto: %(default)s)",
    )
    subparsers = parser.add_subparsers(dest="command", title="grupos", metavar="GRUPO")

    init_parser = subparsers.add_parser(
        "init",
        help="crea la configuracion inicial y el archivo .env",
        description="Crea config/core.yaml y .env desde una plantilla y valida el resultado.",
    )
    init_parser.add_argument(
        "--endpoint",
        metavar="URL",
        help=f"endpoint OpenAI-compatible; si se omite se pregunta (por defecto: {DEFAULT_ENDPOINT})",
    )
    init_parser.add_argument(
        "--template",
        choices=sorted(TEMPLATE_FILES),
        default="minimal",
        help="plantilla de configuracion (por defecto: %(default)s)",
    )
    init_parser.add_argument(
        "--force", action="store_true", help="sobrescribe config/core.yaml y .env si ya existen"
    )

    prompt_parser = _group_parser(
        subparsers, "prompt", "ejecuta inferencias", "Ejecuta prompts mediante los modelos y dominios declarados."
    )
    prompt_subparsers = _action_subparsers(prompt_parser, "prompt_command")
    run_parser = prompt_subparsers.add_parser(
        "run",
        help="ejecuta un prompt",
        description="Ejecuta un prompt contra un modelo local.",
        epilog=(
            "Resolucion: --model tiene prioridad sobre --domain. Sin ambos, "
            "el router selecciona el dominio y el modelo."
        ),
    )
    _add_inference_arguments(run_parser)
    _add_json_argument(run_parser, "resultado")
    _add_identity_arguments(run_parser)

    reasoning_parser = _group_parser(
        subparsers,
        "reasoning",
        "ejecuta razonamiento iterativo",
        "Ejecuta razonamiento controlado con los limites declarados en el perfil.",
    )
    reasoning_subparsers = _action_subparsers(reasoning_parser, "reasoning_command")
    reasoning_run_parser = reasoning_subparsers.add_parser(
        "run",
        help="ejecuta el razonamiento y devuelve el resultado final",
        description="Ejecuta razonamiento iterativo y devuelve su salida final.",
        epilog="--model tiene prioridad sobre --domain; sin ambos se usa el router.",
    )
    _add_inference_arguments(reasoning_run_parser)
    _add_json_argument(reasoning_run_parser, "resultado")
    _add_identity_arguments(reasoning_run_parser)
    reasoning_stream_parser = reasoning_subparsers.add_parser(
        "stream",
        help="emite los eventos del razonamiento mientras se ejecuta",
        description="Ejecuta razonamiento iterativo y muestra cada evento del flujo.",
        epilog="--model tiene prioridad sobre --domain; sin ambos se usa el router.",
    )
    _add_inference_arguments(reasoning_stream_parser)
    _add_json_argument(reasoning_stream_parser, "cada evento como JSONL")
    _add_identity_arguments(reasoning_stream_parser)

    task_parser = _group_parser(
        subparsers, "task", "orquesta tareas multi-modelo",
        "Planifica, enruta, ejecuta, combina y evalua una tarea compleja.",
    )
    task_subparsers = _action_subparsers(task_parser, "task_command")
    task_run_parser = task_subparsers.add_parser(
        "run", help="ejecuta una tarea y muestra sus checkpoints",
        description="Ejecuta task.run y muestra los checkpoints mientras progresa.",
    )
    task_run_parser.add_argument("--prompt", required=True, metavar="TEXTO", help="tarea que se desea ejecutar")
    _add_json_argument(task_run_parser, "cada checkpoint como JSONL")
    _add_identity_arguments(task_run_parser)

    domain_parser = _group_parser(
        subparsers, "domain", "consulta y enruta dominios", "Consulta los dominios declarados o enruta un prompt."
    )
    domain_subparsers = _action_subparsers(domain_parser, "domain_command")
    route_parser = domain_subparsers.add_parser(
        "route",
        help="propone dominio y modelo para un prompt",
        description="Evalua las reglas declaradas y propone el dominio y modelo aplicables.",
    )
    route_parser.add_argument("--prompt", required=True, metavar="TEXTO", help="texto que se desea enrutar")
    route_parser.add_argument(
        "--tag", action="append", default=[], metavar="ETIQUETA", help="etiqueta de ruteo; puede repetirse"
    )
    _add_json_argument(route_parser, "resultado")
    _add_identity_arguments(route_parser)
    domain_list_parser = domain_subparsers.add_parser(
        "list", help="lista los dominios declarados", description="Lista dominios, modelo preferido y estado."
    )
    _add_json_argument(domain_list_parser, "listado")

    model_parser = _group_parser(
        subparsers, "model", "consulta y aprovisiona modelos", "Consulta modelos o descarga los declarados que falten."
    )
    model_subparsers = _action_subparsers(model_parser, "model_command")
    model_list_parser = model_subparsers.add_parser(
        "list", help="lista los modelos conocidos", description="Lista modelos, proveedor, disponibilidad y perfil."
    )
    _add_json_argument(model_list_parser, "listado")
    model_pull_parser = model_subparsers.add_parser(
        "pull",
        help="descarga modelos mediante el provisioner del backend",
        description="Descarga modelos ausentes mediante el provisioner compatible con su proveedor.",
    )
    model_pull_parser.add_argument(
        "models",
        nargs="*",
        metavar="MODELO",
        help="id o nombre de modelo; sin valores procesa todos los modelos declarados",
    )
    _add_json_argument(model_pull_parser, "resultado")

    config_parser = _group_parser(
        subparsers, "config", "valida la configuracion", "Opera sobre la configuracion declarativa del core."
    )
    config_subparsers = _action_subparsers(config_parser, "config_command")
    validate_parser = config_subparsers.add_parser(
        "validate", help="valida el archivo YAML", description="Valida modelos, dominios, perfiles y referencias."
    )
    _add_json_argument(validate_parser, "resultado")

    eval_parser = _group_parser(
        subparsers, "eval", "ejecuta baterias de evaluacion", "Ejecuta evaluaciones de conformidad o smoke."
    )
    eval_subparsers = _action_subparsers(eval_parser, "eval_command")
    eval_run_parser = eval_subparsers.add_parser(
        "run", help="ejecuta una pista de evaluacion", description="Ejecuta los casos de la pista seleccionada."
    )
    eval_run_parser.add_argument(
        "--track",
        choices=["conformance", "smoke"],
        default="conformance",
        help="pista determinista o contra backend real (por defecto: %(default)s)",
    )
    eval_run_parser.add_argument(
        "--battery-dir",
        default="eval/battery",
        metavar="DIRECTORIO",
        help="directorio de la bateria (por defecto: %(default)s)",
    )
    _add_json_argument(eval_run_parser, "resultado completo")

    runtime_parser = _group_parser(
        subparsers, "runtime", "inspecciona runtime, backend y GPU", "Consulta salud y deteccion del entorno de ejecucion."
    )
    runtime_subparsers = _action_subparsers(runtime_parser, "runtime_command")
    health_parser = runtime_subparsers.add_parser(
        "health", help="comprueba la salud del core", description="Informa del core, backend, modelos y protocolo MCP."
    )
    _add_json_argument(health_parser, "informe")
    detect_parser = runtime_subparsers.add_parser(
        "detect", help="detecta runtime, backend y GPU", description="Detecta Python, plataforma, backend y GPU disponible."
    )
    _add_json_argument(detect_parser, "informe")
    return parser


def _group_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    summary: str,
    description: str,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(name, help=summary, description=description)


def _action_subparsers(parser: argparse.ArgumentParser, dest: str) -> argparse._SubParsersAction[argparse.ArgumentParser]:
    return parser.add_subparsers(dest=dest, title="acciones", metavar="ACCION")


def _add_inference_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", required=True, metavar="TEXTO", help="texto que se enviara al modelo")
    parser.add_argument("--domain", metavar="DOMINIO", help="dominio declarado usado para resolver el modelo")
    parser.add_argument("--model", metavar="MODELO", help="modelo directo; tiene prioridad sobre --domain")


def _add_json_argument(parser: argparse.ArgumentParser, content: str) -> None:
    parser.add_argument("--json", action="store_true", help=f"emite {content} en formato JSON")


def _add_identity_arguments(parser: argparse.ArgumentParser) -> None:
    identity = parser.add_argument_group("identidad del request")
    identity.add_argument("--user-id", metavar="ID", help="identificador de usuario; sobrescribe el valor configurado")
    identity.add_argument("--service", metavar="SERVICIO", help="servicio de origen; sobrescribe el valor configurado")
    identity.add_argument("--session-id", metavar="ID", help="identificador opcional de continuidad de sesion")
    identity.add_argument("--domain-tag", metavar="ETIQUETA", help="etiqueta de dominio incluida en identidad y traza")
    identity.add_argument("--namespace", metavar="ESPACIO", help="espacio de identidad incluido en la traza")


def _init(args: argparse.Namespace) -> int:
    config_path = Path("config/core.yaml")
    env_path = Path(".env")
    existing_paths = [path for path in (config_path, env_path) if path.exists()]
    if existing_paths and not args.force:
        paths = ", ".join(str(path) for path in existing_paths)
        raise CoreError("ConfigError", f"files already exist: {paths}; use --force to overwrite", "config")

    endpoint = args.endpoint or _prompt_endpoint()
    template_path = _template_path(args.template)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    env_path.write_text(f"OPENAI_COMPAT_BASE_URL={endpoint}\n", encoding="utf-8")
    load_dotenv(env_path, override=True)
    service.validate_config(config_path=config_path)
    print(f"created {config_path}")
    print(f"created {env_path}")
    print("ok")
    return 0


def _prompt_endpoint() -> str:
    endpoint = input(f"OpenAI-compatible endpoint [{DEFAULT_ENDPOINT}]: ").strip()
    return endpoint or DEFAULT_ENDPOINT


def _template_path(template: str) -> Path:
    return Path(__file__).resolve().parents[2] / "config" / TEMPLATE_FILES[template]


def _prompt_run(args: argparse.Namespace) -> int:
    result = service.run_prompt(
        config_path=args.config,
        prompt=args.prompt,
        model=args.model,
        domain=args.domain,
        identity=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(result["response"])
    return 0


def _reasoning_run(args: argparse.Namespace) -> int:
    result = service.run_reasoning(
        config_path=args.config,
        prompt=args.prompt,
        model=args.model,
        domain=args.domain,
        identity=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(result["output"])
    return 0


def _reasoning_stream(args: argparse.Namespace) -> int:
    for event in service.stream_reasoning(
        config_path=args.config,
        prompt=args.prompt,
        model=args.model,
        domain=args.domain,
        identity=_identity_override(args),
    ):
        if args.json:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{event['type']}\t{event['data']}")
    return 0


def _task_run(args: argparse.Namespace) -> int:
    for event in service.stream_task(
        config_path=args.config,
        prompt=args.prompt,
        identity=_identity_override(args),
    ):
        if args.json:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        elif event["type"] == "task_done":
            print(event["data"]["response"])
        else:
            print(event["type"])
    return 0


def _domain_route(args: argparse.Namespace) -> int:
    result = service.route_domain(
        config_path=args.config,
        prompt=args.prompt,
        tags=args.tag,
        identity=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['domain']}\t{result['model']}\t{result['reason']}")
    return 0


def _domain_list(args: argparse.Namespace) -> int:
    result = service.list_domains(config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for record in result["domains"]:
            print(f"{record['id']}\t{record['preferred_model']}\t{record['status']}")
    return 0


def _model_list(args: argparse.Namespace) -> int:
    result = service.list_models(config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for record in result["models"]:
            print(f"{record['id']}\t{record['provider']}\t{record['available']}\t{record['profile']}")
    return 0


def _model_pull(args: argparse.Namespace) -> int:
    result = service.pull_models(config_path=args.config, model_references=args.models)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for model_name in result["pulled"]:
            print(f"pulled\t{model_name}")
        for model_name in result["present"]:
            print(f"present\t{model_name}")
    return 0


def _config_validate(args: argparse.Namespace) -> int:
    result = service.validate_config(config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("ok")
    return 0


def _eval_run(args: argparse.Namespace) -> int:
    result = service.run_eval(config_path=args.config, battery_dir=args.battery_dir, track=args.track)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['verdict']}\t{result['conformance_digest']}")
    return 0


def _runtime_health(args: argparse.Namespace) -> int:
    result = service.health(config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['status']}\t{result['mcp']['protocol_version']}")
    return 0


def _runtime_detect(args: argparse.Namespace) -> int:
    result = service.detect_runtime(config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        gpu = "gpu" if result["gpu"]["available"] else "no_gpu"
        print(f"{result['status']}\t{gpu}\tpython {result['runtime']['python']}")
    return 0


def _identity_override(args: argparse.Namespace) -> dict[str, str]:
    values = {
        "user_id": args.user_id,
        "service": args.service,
        "session_id": args.session_id,
        "domain_tag": args.domain_tag,
        "namespace": args.namespace,
    }
    return {key: value for key, value in values.items() if value}


def _emit_error(exc: CoreError, *, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"error": exc.to_dict()}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    else:
        field = f" ({exc.field})" if exc.field else ""
        print(f"{exc.type}{field}: {exc.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
