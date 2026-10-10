# TreeGov — Convenciones para Aider

Reglas operativas del proyecto. Aider (hoy respaldo) las lee
automáticamente en cada tarea; OpenCode (herramienta activa) las aplica
como convenciones del repo junto con `AGENTS.md`. NO duplica
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

Si la suite baja de 243/243 tests, no se commitea.

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

**Reglas actualizadas tras migración a Moonshot AI (03/10/2026) y
aprendizajes de las sesiones del 03 y 04/10/2026:**

1. **Un prompt = un archivo.** Cuando un cambio requiere tocar N archivos,
   hacer N sesiones separadas de OpenCode. Se mantiene por claridad de diffs y
   auditoría, no por limitación técnica.

2. **Prosa sin código literal (recomendado, no obligatorio).** Describir la
   estructura en prosa y dejar que Kimi escriba el código. Aunque Moonshot
   no falla con código literal, los prompts en prosa son más fáciles de
   auditar y revisar.

3. **Tamaño máximo orientativo:** hasta ~150 líneas de prosa por prompt
   (antes ~30-100 con NVIDIA NIM). Cambios multi-bloque dentro del mismo
   archivo: permitidos.

4. **Si el cambio es buscar-y-reemplazar trivial (<10 líneas):** evaluar
   hacerlo manualmente en VS Code en lugar de invocar OpenCode. OpenCode rinde
   cuando hay síntesis o análisis; el reemplazo mecánico es más rápido a mano.

5. **Sin archivos innecesarios en contexto.** Al arrancar el agente con
   archivos explícitos, no añadir más archivos al contexto salvo que
   aporten contexto esencial. Cada archivo extra suma tokens.

6. **Verificar SIEMPRE el diff antes de aceptar el edit.** El agente puede
   ocasionalmente "conversar" en lugar de aplicar (patrón documentado en
   `audit_log.md` el 03/10/2026, con Aider). Si falla 2-3 veces seguidas
   sobre el mismo archivo, hacer la edición manual y documentar la excepción.

7. **Nombres de funciones y parámetros en prompts.** Al escribir prompts
   con llamadas a funciones (por ejemplo, `math.isclose(..., abs_tol=1e-3)`),
   verificar el nombre exacto del parámetro. Errores como `abs=` en lugar de
   `abs_tol=` provocan fallos evitables. Es responsabilidad del revisor
   humano validar los nombres antes de enviar el prompt.

8. **Verificación aritmética de valores esperados.** Cuando un test verifica
   un valor calculado a mano (por ejemplo, la raíz QDA más cercana a un
   punto), re-verificar la aritmética antes de fijar el valor. Es más
   rápido re-verificar que corregir el test después.

## Preguntas interactivas del agente

- `Add file to the chat? (Y)es/(N)o`: normalmente `n` — el prompt ya describe
  lo necesario. Aceptar solo si el archivo aporta información no descrita.
- `Create new file? (Y)es/(N)o`: normalmente `y` — es la confirmación para
  aplicar el cambio que crea un archivo nuevo.
- `Apply this edit?`: revisar el diff antes de responder `y`.

## Antes de editar

Si un bloque de texto largo debe insertarse en un archivo, preferir
referencias exactas ("inserta después de X") en lugar de reescribir todo
el archivo (whole edit format).

## Flujo de trabajo

Diseñar → Auditar diseño → Implementar → Testear → Documentar.
Cada cambio de código va acompañado de una entrada en `docs/audit_log.md`.

**Documentación de fase cerrada: nunca se aplaza.** Cuando una sub-fase
cierra, la actualización de audit_log + roadmap + estado_proyecto +
documentos de contexto se hace en el mismo bloque de trabajo. Aplazarlo
desincroniza el contexto y cuesta tiempo de reconstrucción en el
siguiente chat. Excepciones: solo 504/timeout del proveedor o cambio
trivial de 1 línea consolidado en la entrada de bloque.

## Proveedor de IA: Moonshot AI directo (desde 03/10/2026)

Cliente activo desde 09/10/2026: OpenCode 1.18.35, autenticado con key
propia de Moonshot (conexión directa al endpoint `api.moonshot.ai`,
sin la capa intermedia de NVIDIA NIM). Aider 0.86.2 queda como respaldo
documentado. La migración eliminó los 504 recurrentes de NIM que
históricamente forzaban aplazamientos, y el consumo de tokens con
OpenCode 1.18.35 + Moonshot directo es sustancialmente menor que con
Aider.

- **Modelo:** `moonshot/kimi-k3`.
- **Endpoint:** `https://api.moonshot.ai/v1` (LiteLLM lo conoce por defecto).
- **Variable de entorno:** `$env:MOONSHOT_API_KEY` (pedir con
  `Read-Host -AsSecureString`).
- **Metadata:** `~/.aider.model.metadata.json` (contexto y costes) +
  `~/.aider.model.settings.yml` (Kimi K3 exige `use_temperature: false`).
- **Ventaja frente a NVIDIA NIM:** sin 504, sin necesidad de trocear prompts
  por tiempo de servidor, contexto 1M completo.
- **Verificación obligatoria sigue aplicando:** `git diff` + `pytest` antes
  de aceptar cualquier cambio.