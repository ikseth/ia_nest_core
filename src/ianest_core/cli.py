from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from ianest_core.config import load_config, validate_config_dict
from ianest_core.evaluation import run_eval
from ianest_core.errors import CoreError
from ianest_core.registry import ModelRegistry
from ianest_core.runtime import DomainRuntime, PromptRuntime


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prompt" and args.prompt_command == "run":
            return _prompt_run(args)
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
    except CoreError as exc:
        return _emit_error(exc, json_output=getattr(args, "json", False))
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ianest")
    parser.add_argument("--config", default="config/core.yaml", help="ruta de configuracion YAML")
    subparsers = parser.add_subparsers(dest="command")

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
    return parser


def _prompt_run(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    runtime = PromptRuntime(config)
    result = runtime.run(
        prompt=args.prompt,
        model_id=args.model,
        domain_id=args.domain,
        identity_override=_identity_override(args),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(result.response)
    return 0


def _domain_route(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    runtime = DomainRuntime(config)
    result = runtime.route(
        prompt=args.prompt,
        identity_override=_identity_override(args),
        tags=args.tag,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result.domain}\t{result.model}\t{result.reason}")
    return 0


def _domain_list(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    records = ModelRegistry(config).domain_records()
    if args.json:
        print(json.dumps({"domains": records}, ensure_ascii=False, sort_keys=True))
    else:
        for record in records:
            print(f"{record['id']}\t{record['preferred_model']}\t{record['status']}")
    return 0


def _model_list(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    records = ModelRegistry(config).model_records()
    if args.json:
        print(json.dumps({"models": records}, ensure_ascii=False, sort_keys=True))
    else:
        for record in records:
            print(f"{record['id']}\t{record['provider']}\t{record['available']}\t{record['profile']}")
    return 0


def _config_validate(args: argparse.Namespace) -> int:
    with Path(args.config).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    validate_config_dict(raw)
    payload = {"status": "ok"}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("ok")
    return 0


def _eval_run(args: argparse.Namespace) -> int:
    result = run_eval(battery_dir=args.battery_dir, track=args.track, config_path=args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['verdict']}\t{result['conformance_digest']}")
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
