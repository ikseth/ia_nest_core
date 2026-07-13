from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ianest_core.config import load_config
from ianest_core.errors import CoreError
from ianest_core.runtime import PromptRuntime


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prompt" and args.prompt_command == "run":
            return _prompt_run(args)
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

