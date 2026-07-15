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
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _init(args)
        if args.command == "prompt" and args.prompt_command == "run":
            return _prompt_run(args)
        if args.command == "reasoning" and args.reasoning_command == "run":
            return _reasoning_run(args)
        if args.command == "reasoning" and args.reasoning_command == "stream":
            return _reasoning_stream(args)
        if args.command == "domain" and args.domain_command == "route":
            return _domain_route(args)
        if args.command == "domain" and args.domain_command == "list":
            return _domain_list(args)
        if args.command == "model" and args.model_command == "list":
            return _model_list(args)
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
    parser = argparse.ArgumentParser(prog="ianest")
    parser.add_argument("--config", default="config/core.yaml", help="ruta de configuracion YAML")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--endpoint")
    init_parser.add_argument("--template", choices=sorted(TEMPLATE_FILES), default="minimal")
    init_parser.add_argument("--force", action="store_true")

    prompt_parser = subparsers.add_parser("prompt")
    prompt_subparsers = prompt_parser.add_subparsers(dest="prompt_command")
    run_parser = prompt_subparsers.add_parser("run")
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--domain")
    run_parser.add_argument("--model")
    run_parser.add_argument("--json", action="store_true")
    run_parser.add_argument("--user-id")
    run_parser.add_argument("--service")
    run_parser.add_argument("--session-id")
    run_parser.add_argument("--domain-tag")
    run_parser.add_argument("--namespace")

    reasoning_parser = subparsers.add_parser("reasoning")
    reasoning_subparsers = reasoning_parser.add_subparsers(dest="reasoning_command")
    reasoning_run_parser = reasoning_subparsers.add_parser("run")
    reasoning_run_parser.add_argument("--prompt", required=True)
    reasoning_run_parser.add_argument("--domain")
    reasoning_run_parser.add_argument("--model")
    reasoning_run_parser.add_argument("--json", action="store_true")
    reasoning_run_parser.add_argument("--user-id")
    reasoning_run_parser.add_argument("--service")
    reasoning_run_parser.add_argument("--session-id")
    reasoning_run_parser.add_argument("--domain-tag")
    reasoning_run_parser.add_argument("--namespace")
    reasoning_stream_parser = reasoning_subparsers.add_parser("stream")
    reasoning_stream_parser.add_argument("--prompt", required=True)
    reasoning_stream_parser.add_argument("--domain")
    reasoning_stream_parser.add_argument("--model")
    reasoning_stream_parser.add_argument("--json", action="store_true")
    reasoning_stream_parser.add_argument("--user-id")
    reasoning_stream_parser.add_argument("--service")
    reasoning_stream_parser.add_argument("--session-id")
    reasoning_stream_parser.add_argument("--domain-tag")
    reasoning_stream_parser.add_argument("--namespace")

    domain_parser = subparsers.add_parser("domain")
    domain_subparsers = domain_parser.add_subparsers(dest="domain_command")
    route_parser = domain_subparsers.add_parser("route")
    route_parser.add_argument("--prompt", required=True)
    route_parser.add_argument("--tag", action="append", default=[])
    route_parser.add_argument("--json", action="store_true")
    route_parser.add_argument("--user-id")
    route_parser.add_argument("--service")
    route_parser.add_argument("--session-id")
    route_parser.add_argument("--domain-tag")
    route_parser.add_argument("--namespace")
    domain_list_parser = domain_subparsers.add_parser("list")
    domain_list_parser.add_argument("--json", action="store_true")

    model_parser = subparsers.add_parser("model")
    model_subparsers = model_parser.add_subparsers(dest="model_command")
    model_list_parser = model_subparsers.add_parser("list")
    model_list_parser.add_argument("--json", action="store_true")

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    validate_parser = config_subparsers.add_parser("validate")
    validate_parser.add_argument("--json", action="store_true")

    eval_parser = subparsers.add_parser("eval")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    eval_run_parser = eval_subparsers.add_parser("run")
    eval_run_parser.add_argument("--track", choices=["conformance", "smoke"], default="conformance")
    eval_run_parser.add_argument("--battery-dir", default="eval/battery")
    eval_run_parser.add_argument("--json", action="store_true")

    runtime_parser = subparsers.add_parser("runtime")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command")
    health_parser = runtime_subparsers.add_parser("health")
    health_parser.add_argument("--json", action="store_true")
    detect_parser = runtime_subparsers.add_parser("detect")
    detect_parser.add_argument("--json", action="store_true")
    return parser


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
