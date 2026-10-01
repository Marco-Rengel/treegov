# TreeGov — Convenciones para Aider

Reglas operativas que Aider lee automáticamente en cada tarea. NO duplica
filosofía completa (ver `.treegovrules`); son recordatorios operativos.

## Sala limpia (inviolable)

- `backend_v3/` — capa analítica pura. Cero imports de Qt/PySide6.
- `frontend_v3/` — capa de presentación. Cero imports de numpy/pandas/scipy.
- Comunicación exclusiva vía `backend_v3.session_state.Session`.

Un test AST (`tests/test_gui_smoke::test_frontend_clean_room`) verifica
que no se rompa esta separación.

## Verificación obligatoria

Después de CADA tarea de edición, el humano verifica con:

    python -m pytest tests -q
    git status
    git diff --stat

Si la suite baja de 178/178 tests, no se commitea.

## Comentarios y docs

- Código: docstrings y comentarios en **inglés**.
- Docs internos (audit_log, contexto, etc.): **español**.
- Cero referencias a software privativo (SPSS, SAS, Stata, Answer Tree).

## Tests

- Duales: ejecutables con `pytest` o `python tests/test_X.py`.
- `QT_QPA_PLATFORM=offscreen` para tests GUI.
- Valores verificados a mano, no autoreferencias.

## Caja blanca

Prohibido importar: sklearn, statsmodels, xgboost, lightgbm, catboost.
Toda fórmula estadística con cita bibliográfica explícita.

## Prompts grandes

Si la tarea implica insertar >100 líneas de contenido textual (no código
referenciado), trocear en 2-3 prompts. Aider+Kimi vía NIM puede dar 504.

## Antes de editar

Si un bloque de texto largo debe insertarse en un archivo, preferir
referencias exactas ("inserta después de X") en lugar de reescribir todo
el archivo (whole edit format).

## Flujo de trabajo

Diseñar → Auditar diseño → Implementar → Testear → Documentar.
Cada cambio de código va acompañado de una entrada en `docs/audit_log.md`.