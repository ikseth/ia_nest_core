#!/usr/bin/env python3
"""Smoke de la superficie REST de un core ya arrancado.

Existe porque un informe que NARRA una verificacion es peor que no tenerlo: la
sustituye en vez de guiarla. Esto se ejecuta y devuelve un codigo de salida.

La suite y la CLI leen del disco en cada invocacion, asi que actualizar el arbol
las actualiza. Un servicio REST ya arrancado NO: sigue con el codigo que cargo
en memoria. Por eso este smoke va contra la RED, que es la superficie que
consumen las capas de encima, y por eso lo primero que hace es preguntarle al
servicio que version cree ser.

Que comprueba y que NO. Comprueba la SUPERFICIE: que las capacidades estan, que
`/task/run` devuelve JSON y `/task/stream` es SSE -la ruptura de v0.4.0-, que
`backend.gpu` viaja como lista y sin filtrar la topologia, y que un cliente que
siga enviando el `tags` retirado no recibe error. NO juzga la calidad de la
respuesta del modelo: un PASA con modelos fake es un PASA de forma, no de
contenido. Las lineas del gate de la fase v0.4-B3 -`degradations`,
`requirements_covered`, `effort`, `stop_reason`- se IMPRIMEN para que se lean;
la unica que se senala en la tabla es la convergencia, porque el gate declarado
no la miraba.

Uso:

    python3 deploy/smoke_rest.py http://<host>:<puerto> [--expect-version 0.4.0]

Codigo de salida 0 si todo pasa, 1 si algo falla. Solo biblioteca estandar: se
puede copiar a la maquina que sea y ejecutarlo sin instalar nada.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TIMEOUT = 300


class Fallo(Exception):
    pass


def llamar(base: str, metodo: str, ruta: str, cuerpo: dict | None = None) -> tuple[dict, str]:
    """Devuelve (payload, content_type). Levanta Fallo con el detalle del error."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        base.rstrip("/") + ruta,
        data=datos,
        method=metodo,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            crudo = respuesta.read().decode("utf-8")
            tipo = respuesta.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")[:300]
        raise Fallo(f"HTTP {exc.code}: {detalle}") from exc
    except urllib.error.URLError as exc:
        raise Fallo(f"sin respuesta: {exc.reason}") from exc
    try:
        return json.loads(crudo), tipo
    except json.JSONDecodeError:
        return {"_crudo": crudo}, tipo


def sse(base: str, ruta: str, cuerpo: dict) -> tuple[list[str], str]:
    """Consume un flujo SSE y devuelve (tipos de evento, content_type)."""
    peticion = urllib.request.Request(
        base.rstrip("/") + ruta,
        data=json.dumps(cuerpo).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    eventos: list[str] = []
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            tipo = respuesta.headers.get("Content-Type", "")
            for linea in respuesta:
                texto = linea.decode("utf-8", "replace").strip()
                if texto.startswith("event:"):
                    eventos.append(texto.split(":", 1)[1].strip())
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")[:300]
        raise Fallo(f"HTTP {exc.code}: {detalle}") from exc
    except urllib.error.URLError as exc:
        raise Fallo(f"sin respuesta: {exc.reason}") from exc
    return eventos, tipo


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise Fallo(mensaje)


# --- comprobaciones ---------------------------------------------------------
# Cada una devuelve una linea de resumen, o levanta Fallo con el motivo.


def c_capability_list(base: str, ctx: dict) -> str:
    payload, _ = llamar(base, "GET", "/capability/list")
    nombres = {c["name"] for c in payload["capabilities"]}
    ctx["capacidades"] = nombres
    ctx["core_version"] = payload.get("core_version")
    exigir(bool(ctx["core_version"]), "capability.list no publica core_version")
    # Las tres que estrena v0.4.0. Si el proceso es viejo, aqui se cae.
    for esperada in ("capability.list", "task.plan", "task.stream"):
        exigir(esperada in nombres, f"falta la capacidad {esperada}")
    return f"{len(nombres)} capacidades, core_version {ctx['core_version']}"


def c_runtime_health(base: str, ctx: dict) -> str:
    payload, _ = llamar(base, "GET", "/runtime/health")
    exigir("gpu" in payload, "runtime.health no publica gpu (runtime local)")
    backend = payload.get("backend", {})
    exigir("gpu" in backend, "runtime.health no publica backend.gpu (ADR 0049)")
    exigir(isinstance(backend["gpu"], list), "backend.gpu deberia ser una LISTA")
    crudo = json.dumps(payload)
    exigir("endpoint" not in crudo, "backend.gpu filtra la palabra endpoint")
    # `unknown` sin su `reason` obliga a repetir el diagnostico a mano, y sus tres
    # causas piden acciones distintas: no_models_loaded es benigno, y
    # backend_unreachable NO lo es aunque la inferencia funcione -pasa cuando la
    # sonda mira a un endpoint sin resolver-.
    estados = [
        e.get("status") if e.get("status") != "unknown" else f"unknown/{e.get('reason')}"
        for e in backend["gpu"]
    ]
    local = payload["gpu"].get("available")
    gate = "PASA" if local is False and "in_use" in estados else "-"
    return f"gpu local available={local}, backend.gpu={estados}, gate ADR 0049: {gate}"


def c_config_validate(base: str, ctx: dict) -> str:
    payload, _ = llamar(base, "POST", "/config/validate", {})
    exigir(payload.get("status") == "ok", f"config invalida: {payload}")
    return "ok"


def c_domain_route(base: str, ctx: dict) -> str:
    payload, _ = llamar(base, "POST", "/domain/route", {"prompt": "escribe un bucle for en python"})
    exigir(bool(payload.get("domain")), f"sin dominio: {payload}")
    return f"domain={payload['domain']}, confidence={payload.get('confidence')}"


def c_domain_route_sin_tags(base: str, ctx: dict) -> str:
    # v0.4.0 retira `tags`. Un cliente REST que lo siga enviando NO recibe error:
    # eso es lo declarado en el CHANGELOG, y lo comprobamos en vez de suponerlo.
    payload, _ = llamar(
        base, "POST", "/domain/route", {"prompt": "cual es la derivada de x cubo", "tags": ["viejo"]}
    )
    exigir(bool(payload.get("domain")), f"tags retirado rompio la llamada: {payload}")
    return f"tolerado, domain={payload['domain']}"


def c_prompt_run(base: str, ctx: dict) -> str:
    payload, _ = llamar(base, "POST", "/prompt/run", {"prompt": "di hola en una linea"})
    texto = payload.get("response") or ""
    exigir(bool(texto.strip()), f"respuesta vacia: {payload}")
    return f"{len(texto)} caracteres, modelo {payload.get('trace', {}).get('model')}"


def c_task_plan(base: str, ctx: dict) -> str:
    prompt = (
        "Necesito tres cosas independientes: 1) una definicion de kernel, "
        "2) un script bash que cuente ficheros por extension, "
        "3) la derivada de x cubo"
    )
    payload, _ = llamar(base, "POST", "/task/plan", {"prompt": prompt})
    exigir("degradations" in payload, "task.plan no publica degradations (ficha v0.4/0007)")
    exigir("requirements" in payload, "task.plan no publica requirements")
    ctx["plan"] = payload
    ctx["plan_prompt"] = prompt
    return (
        f"{len(payload['plan'])} subtareas, {len(payload['requirements'])} requisitos, "
        f"degradations={payload['degradations']}"
    )


def c_task_run_es_json(base: str, ctx: dict) -> str:
    # LA ruptura de v0.4.0: /task/run devuelve JSON, ya no SSE.
    payload, tipo = llamar(base, "POST", "/task/run", {"prompt": "resume que es un kernel"})
    exigir("event-stream" not in tipo, f"/task/run sigue siendo SSE: {tipo}. Proceso viejo?")
    exigir("application/json" in tipo, f"content-type inesperado: {tipo}")
    exigir("stop_reason" in payload, f"sin stop_reason: {list(payload)}")
    return f"JSON, stop_reason={payload['stop_reason']}, subtareas={len(payload.get('subtasks', []))}"


def c_task_run_con_plan(base: str, ctx: dict) -> str:
    # La via que ejercita extended: la respuesta de task.plan ES la peticion de
    # task.run (ADR 0048), con los campos como hermanos y no anidados.
    plan = ctx.get("plan")
    exigir(plan is not None, "no hay plan previo; task.plan fallo antes")
    payload, _ = llamar(
        base,
        "POST",
        "/task/run",
        {
            "prompt": ctx["plan_prompt"],
            "plan": plan["plan"],
            "requirements": plan["requirements"],
            "effort": plan["effort"],
        },
    )
    exigir(payload.get("plan_attempts") == 0, f"plan_attempts deberia ser 0: {payload.get('plan_attempts')}")
    # La cuarta linea del gate que pidio extended (hallazgo 1): mirar COMO termino.
    convergio = payload.get("stop_reason") == "task_done"
    return (
        f"stop_reason={payload.get('stop_reason')}"
        f"{'' if convergio else '  <-- NO convergio'}, "
        f"covered={payload.get('requirements_covered')}, "
        f"degradations={payload.get('degradations')}, "
        f"plan_attempts={payload.get('plan_attempts')}"
    )


def c_task_stream_es_sse(base: str, ctx: dict) -> str:
    # La otra mitad de la ruptura: el flujo vive ahora aqui.
    eventos, tipo = sse(base, "/task/stream", {"prompt": "resume que es un kernel"})
    exigir("event-stream" in tipo, f"/task/stream no es SSE: {tipo}")
    exigir(bool(eventos), "flujo sin un solo evento")
    exigir("task_done" in eventos or "error" in eventos, f"flujo sin cierre: {eventos}")
    return f"SSE, {len(eventos)} eventos, ultimo={eventos[-1]}"


# El orden NO es cosmetico: `prompt.run` va ANTES que `runtime.health` para que
# la propia sonda encuentre un modelo cargado. `in_use` exige un modelo cargado en
# ese instante, y el backend lo descarga al vencer su `keep_alive`; consultar
# primero da `unknown/no_models_loaded`, que seria correcto y parece un fallo.
#
# La inferencia de calentamiento la hace el smoke POR REST, no el operador desde
# su shell. Calentar a mano con la CLI parece equivalente y no lo es: la CLI no
# resuelve la variable de configuracion del core que la REST si respeta (hallazgo
# 4 del handoff de extended del 2026-08-18), asi que lanzada fuera del directorio
# con el `.env` falla en silencio y deja la sonda sin nada que ver. Ese error de
# metodo ya se ha cobrado tres pasadas de laboratorio.
COMPROBACIONES = [
    ("capability.list", c_capability_list),
    ("config.validate", c_config_validate),
    ("domain.route", c_domain_route),
    ("domain.route sin tags", c_domain_route_sin_tags),
    ("prompt.run", c_prompt_run),
    ("runtime.health", c_runtime_health),
    ("task.plan", c_task_plan),
    ("task.run es JSON", c_task_run_es_json),
    ("task.run con plan", c_task_run_con_plan),
    ("task.stream es SSE", c_task_stream_es_sse),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke por REST de un core arrancado.")
    parser.add_argument("base_url", help="Base del servicio REST, p.ej. http://host:8080")
    parser.add_argument(
        "--expect-version",
        default=None,
        help="Version que el servicio DEBE declarar. Si no coincide, el proceso es viejo.",
    )
    args = parser.parse_args()

    ctx: dict = {}
    fallos = 0
    print(f"smoke REST contra {args.base_url}\n")
    for nombre, comprobacion in COMPROBACIONES:
        inicio = time.monotonic()
        try:
            resumen = comprobacion(args.base_url, ctx)
            estado = "PASA"
        except Fallo as exc:
            resumen = str(exc)
            estado = "FALLA"
            fallos += 1
        except Exception as exc:  # forma inesperada: tambien es un fallo del smoke
            resumen = f"{type(exc).__name__}: {exc}"
            estado = "FALLA"
            fallos += 1
        ms = int((time.monotonic() - inicio) * 1000)
        print(f"  {estado:5}  {nombre:24} {ms:>7} ms  {resumen}")

    declarada = ctx.get("core_version")
    if args.expect_version and declarada != args.expect_version:
        print(
            f"\n  FALLA  core_version                    el servicio declara "
            f"{declarada!r} y se esperaba {args.expect_version!r}."
            f"\n         Un arbol actualizado NO reinicia un proceso ya arrancado:"
            f"\n         reinstala y reinicia los servicios antes de creerte el smoke."
        )
        fallos += 1

    print(f"\nveredicto: {'PASA' if fallos == 0 else f'FALLA ({fallos})'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
