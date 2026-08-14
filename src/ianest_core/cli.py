from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

from ianest_core import service
from ianest_core.capabilities import CAPABILITIES, CLI_GROUPS, Capability, CapabilityParam, CliInput
from ianest_core.dotenv import load_dotenv
from ianest_core.errors import CoreError

DEFAULT_ENDPOINT = "http://localhost:11434/v1"
TEMPLATE_FILES = {
    "minimal": "core.example.yaml",
    "lab": "core.lab.example.yaml",
}
_MISSING = object()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    load_dotenv()
    try:
        capability_name = _capability_name(args)
        capability = next((item for item in CAPABILITIES if item.name == capability_name), None)
        if capability is not None:
            _resolve_cli_inputs(args, capability)
        renderer = _RENDERS.get(capability_name)
        if renderer is not None:
            return renderer(args)
    except CoreError as exc:
        return _emit_error(exc, json_output=getattr(args, "json", False))
    _print_group_help(parser, args.command)
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
    for group in CLI_GROUPS:
        capabilities = _cli_capabilities(group.name)
        direct = [capability for capability in capabilities if capability.cli.action is None]
        if direct:
            assert len(direct) == 1
            _add_capability_parser(subparsers, direct[0], group.name, direct[0].summary)
            continue

        group_parser = _group_parser(subparsers, group.name, group.summary, group.description)
        action_subparsers = _action_subparsers(group_parser, f"{group.name}_command")
        for capability in capabilities:
            projection = capability.cli
            assert projection is not None and projection.action is not None
            _add_capability_parser(action_subparsers, capability, projection.action, capability.summary)
            for alias in projection.aliases:
                _add_capability_parser(
                    action_subparsers,
                    capability,
                    alias,
                    dict(projection.alias_summaries)[alias],
                )
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


def _cli_capabilities(group: str) -> list[Capability]:
    return sorted(
        (
            capability
            for capability in CAPABILITIES
            if capability.cli is not None and capability.cli.group == group
        ),
        key=_cli_capability_order,
    )


def _cli_capability_order(capability: Capability) -> tuple[int, str]:
    projection = capability.cli
    assert projection is not None
    return projection.order, capability.name


def _add_capability_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    capability: Capability,
    action: str,
    summary: str,
) -> None:
    projection = capability.cli
    assert projection is not None
    parser = subparsers.add_parser(
        action,
        help=summary,
        description=projection.description,
        epilog=projection.epilog,
    )
    cli_input_targets = {target for input in projection.inputs for target in input.targets}
    for parameter in capability.params:
        if parameter.cli:
            _add_capability_parameter(
                parser,
                parameter,
                suppress_default=parameter.name in cli_input_targets,
            )
    for input in projection.inputs:
        _add_cli_input(parser, input)
    for flag in projection.flags:
        parser.add_argument(
            f"--{flag}",
            action="store_true",
            help=dict(projection.flag_help)[flag],
        )
    if capability.identity:
        _add_identity_arguments(parser)


def _add_capability_parameter(
    parser: argparse.ArgumentParser,
    parameter: CapabilityParam,
    *,
    suppress_default: bool = False,
) -> None:
    if parameter.type == "array":
        parser.add_argument(
            parameter.name,
            nargs="*",
            metavar=parameter.metavar,
            help=parameter.summary,
        )
        return

    argument = f"--{parameter.name.replace('_', '-')}"
    if parameter.type == "boolean":
        parser.add_argument(argument, action="store_true", help=parameter.summary)
        return

    kwargs: dict[str, object] = {
        "help": parameter.summary,
        "required": parameter.required,
    }
    if parameter.choices is not None:
        kwargs["choices"] = parameter.choices
    if parameter.default is not None:
        kwargs["default"] = parameter.default
    elif suppress_default:
        kwargs["default"] = argparse.SUPPRESS
    if parameter.metavar is not None:
        kwargs["metavar"] = parameter.metavar
    parser.add_argument(argument, **kwargs)


def _add_cli_input(parser: argparse.ArgumentParser, input: CliInput) -> None:
    parser.add_argument(
        f"--{input.name}",
        metavar=input.metavar,
        help=input.summary,
    )


def _resolve_cli_inputs(args: argparse.Namespace, capability: Capability) -> None:
    projection = capability.cli
    if projection is None:
        return
    for input in projection.inputs:
        path = getattr(args, input.name.replace("-", "_"), None)
        if path is None:
            continue
        payload = _read_cli_input(input, Path(path))
        for target in input.targets:
            if target in payload and getattr(args, target, _MISSING) is _MISSING:
                setattr(args, target, payload[target])
    for parameter in capability.params:
        if not hasattr(args, parameter.name):
            setattr(args, parameter.name, parameter.default)


def _read_cli_input(input: CliInput, path: Path) -> dict[str, object]:
    if input.source != "json_file":  # pragma: no cover - guarded by catalog vocabulary
        raise AssertionError(f"unsupported CLI input source: {input.source}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CoreError("ConfigError", f"cannot read {path}: {exc}", input.name) from exc
    except json.JSONDecodeError as exc:
        raise CoreError("ConfigError", f"invalid JSON in {path}: {exc.msg}", input.name) from exc
    if not isinstance(payload, dict):
        raise CoreError("ConfigError", f"JSON input {path} must be an object", input.name)
    return payload


def _print_group_help(parser: argparse.ArgumentParser, command: str | None) -> None:
    if command is not None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                group_parser = action.choices.get(command)
                if group_parser is not None:
                    group_parser.print_help()
                    return
    parser.print_help()


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


def _prompt_stream(args: argparse.Namespace) -> int:
    started_at: float | None = None
    for event in service.stream_prompt(
        config_path=args.config,
        prompt=args.prompt,
        model=args.model,
        domain=args.domain,
        identity=_identity_override(args),
    ):
        if args.verbose and started_at is None:
            started_at = time.monotonic()
        if args.json:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        elif event["type"] == "token":
            print(event["data"]["text"], end="", flush=True)
        elif event["type"] != "done":
            _emit_progress(
                "Prompt en curso",
                quiet=args.quiet,
                verbose=args.verbose,
                started_at=started_at,
            )
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
    started_at: float | None = None
    for event in service.stream_reasoning(
        config_path=args.config,
        prompt=args.prompt,
        model=args.model,
        domain=args.domain,
        identity=_identity_override(args),
    ):
        if args.verbose and started_at is None:
            started_at = time.monotonic()
        if args.json:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        elif event["type"] == "done":
            print(event["data"]["output"])
        elif event["type"] == "token":
            print(event["data"]["text"], end="", flush=True)
        else:
            _emit_progress(
                _reasoning_progress(event, verbose=args.verbose),
                quiet=args.quiet,
                verbose=args.verbose,
                started_at=started_at,
            )
    return 0


def _task_run(args: argparse.Namespace) -> int:
    answer_was_streamed = False
    exit_code = 0
    started_at: float | None = None
    for event in service.stream_task(
        config_path=args.config,
        prompt=args.prompt,
        mode=args.mode,
        effort=args.effort,
        plan=args.plan,
        requirements=args.requirements,
        identity=_identity_override(args),
    ):
        if args.verbose and started_at is None:
            started_at = time.monotonic()
        if event["type"] == "task_done":
            if args.json:
                print(json.dumps(event, ensure_ascii=False, sort_keys=True))
            elif not answer_was_streamed:
                print(event["data"]["response"])
            for degradation in event["data"].get("degradations", []):
                if isinstance(degradation, dict):
                    _emit_task_degradation(degradation)
            stop_reason = event["data"].get("stop_reason", "task_done")
            if stop_reason != "task_done":
                _emit_task_stop(str(stop_reason), event["data"].get("response"))
                exit_code = 1
        elif args.json:
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        elif event["type"] == "answer_chunk":
            if answer_was_streamed:
                print("\n\n", end="")
            print(event["data"]["text"].strip(), end="", flush=True)
            answer_was_streamed = True
        else:
            _emit_progress(
                _task_progress(event, verbose=args.verbose),
                quiet=args.quiet,
                verbose=args.verbose,
                started_at=started_at,
            )
    return exit_code


def _task_stream(args: argparse.Namespace) -> int:
    for event in service.stream_task(
        config_path=args.config,
        prompt=args.prompt,
        mode=args.mode,
        effort=args.effort,
        identity=_identity_override(args),
    ):
        print(json.dumps(event, ensure_ascii=False, sort_keys=True))
    return 0


def _task_plan(args: argparse.Namespace) -> int:
    result = service.plan_task(
        config_path=args.config,
        prompt=args.prompt,
        effort=args.effort,
        identity=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for subtask in result["plan"]:
            prompt = str(subtask["prompt"]).replace("\n", " ")
            print(f"{subtask['index']}\t{subtask['domain']}\t{prompt[:80]}")
    return 0


def _emit_progress(
    message: str,
    *,
    quiet: bool,
    verbose: bool = False,
    started_at: float | None = None,
) -> None:
    if not quiet:
        if verbose and started_at is not None:
            elapsed_s = time.monotonic() - started_at
            message = f"[{elapsed_s:5.1f}s] {message}"
        print(message, file=sys.stderr)


def _emit_task_stop(stop_reason: str, response: object) -> None:
    message = f"Tarea cortada: {stop_reason}."
    if response:
        message += " Se devuelve lo producido hasta el corte."
    else:
        message += " No se produjo respuesta."
    print(message, file=sys.stderr)


def _emit_task_degradation(degradation: dict[str, object]) -> None:
    print(
        "Tarea degradada: "
        f"{degradation.get('stage')} ({degradation.get('reason')} -> {degradation.get('action')}).",
        file=sys.stderr,
    )


def _reasoning_progress(event: dict[str, object], *, verbose: bool = False) -> str:
    if event["type"] == "step":
        data = event.get("data")
        iteration = data.get("iteration") if isinstance(data, dict) else None
        if verbose:
            done = data.get("done") if isinstance(data, dict) else None
            return f"Paso {iteration} (done={done})"
        return f"Paso {iteration} completado" if iteration is not None else "Paso completado"
    return "Razonamiento en curso"


def _task_progress(event: dict[str, object], *, verbose: bool = False) -> str:
    event_type = event["type"]
    data = event.get("data")
    payload = data if isinstance(data, dict) else {}
    if event_type == "task_received":
        return "Tarea recibida"
    if event_type == "plan_ready":
        items = payload.get("units", payload.get("plan", []))
        count = len(items) if isinstance(items, list) else 0
        if verbose:
            noun = "unidades" if "units" in payload else "subtareas"
            return f"Plan: {count} {noun}"
        return f"Plan listo: {count} unidades"
    if event_type == "subtask_done":
        if verbose:
            iteration = f" (iter {payload['iteration']})" if "iteration" in payload else ""
            return (
                f"  subtarea {payload.get('index')}{iteration} "
                f"-> {payload.get('domain')} / {payload.get('model')}"
            )
        return "Subtarea completada"
    if event_type == "coverage_updated":
        completed = payload.get("completed", [])
        pending = payload.get("pending", [])
        failed = payload.get("failed", [])
        completed_count = len(completed) if isinstance(completed, list) else 0
        pending_count = len(pending) if isinstance(pending, list) else 0
        failed_count = len(failed) if isinstance(failed, list) else 0
        total = completed_count + pending_count + failed_count
        if verbose:
            return (
                f"  cobertura {completed_count}/{total} "
                f"(pendientes {pending_count}, fallidas {failed_count})"
            )
        return f"Cobertura actualizada: {completed_count}/{total}"
    if event_type == "iteration_end":
        iteration = payload.get("iteration")
        if verbose:
            decision = f": {payload['decision']}" if "decision" in payload else ""
            return f"Iteracion {iteration}{decision}"
        return f"Iteracion {iteration} completada" if iteration is not None else "Iteracion completada"
    if event_type == "combine_ready":
        return "Respuesta preparada" if payload.get("response") else "Combinacion sin respuesta"
    return "Tarea en curso"


def _domain_route(args: argparse.Namespace) -> int:
    result = service.route_domain(
        config_path=args.config,
        prompt=args.prompt,
        identity=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['domain']}\t{result['model']}\t{result['reason']}")
    return 0


def _capability_list(args: argparse.Namespace) -> int:
    result = service.list_capabilities()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for capability in result["capabilities"]:
            print(f"{capability['name']}\t{capability['summary']}")
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


def _capability_name(args: argparse.Namespace) -> str | None:
    if args.command is None:
        return None
    action = getattr(args, f"{args.command}_command", None)
    return f"{args.command}.{action}" if action is not None else args.command


_RENDERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": _init,
    "prompt.run": _prompt_run,
    "prompt.stream": _prompt_stream,
    "reasoning.run": _reasoning_run,
    "reasoning.stream": _reasoning_stream,
    "task.plan": _task_plan,
    "task.run": _task_run,
    "task.stream": _task_stream,
    "capability.list": _capability_list,
    "domain.route": _domain_route,
    "domain.list": _domain_list,
    "model.list": _model_list,
    "model.pull": _model_pull,
    "config.validate": _config_validate,
    "eval.run": _eval_run,
    "runtime.health": _runtime_health,
    "runtime.detect": _runtime_detect,
}

assert set(_RENDERS) == {
    capability.name
    for capability in CAPABILITIES
    if capability.cli is not None
} | {
    f"{capability.cli.group}.{alias}"
    for capability in CAPABILITIES
    if capability.cli is not None
    for alias in capability.cli.aliases
}


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
