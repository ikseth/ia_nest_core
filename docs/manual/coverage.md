# Modo coverage de task.run

Usa `coverage` cuando la tarea tenga unidades enumerables y verificables:

    ianest --config config/core.yaml task run \
      --mode coverage \
      --prompt "Enumera los ocho planetas y explica cada uno"

`pipeline` sigue siendo el modo por defecto. REST acepta `mode` en
`POST /task/run` y MCP en la herramienta `task.run`, con el mismo default.

Durante el streaming, `answer_chunk` entrega texto aceptado de forma
incremental. `coverage_updated` entrega un snapshot del ledger con unidades
completadas, pendientes y fallidas. Los demas checkpoints conservan su
comportamiento.

Ademas de los cortes comunes, coverage puede terminar por `max_chunks`,
`max_total_tokens` o `no_progress`. Solo `stop_reason=task_done` implica
`coverage_complete=true`.

El resultado incluye `coverage` con `completed_units`, `failed_units`,
`pending_units`, `chunk_index`, unidades resueltas, reintentos y contadores
de tokens. Tambien incluye los fragmentos aceptados en `chunks`.
