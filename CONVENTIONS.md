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

Si la suite baja de 434/434 tests, no se commitea.

**Nunca verificar entre tareas.** La caché de prompt de Moonshot expira
a los 5 minutos de inactividad. Verificar en PowerShell entre cada
tarea destruye la caché y multiplica el coste. Regla: hacer varias
tareas seguidas en la misma sesión de OpenCode, verificar todo en
bloque al final, luego commit. Ver sección "## Trabajo en ráfaga" más
abajo.

## Trabajo en ráfaga

La caché de prompt de Moonshot funciona solo si el prefijo entre
peticiones es idéntico y hay menos de 5 minutos entre ellas.
Verificado empíricamente el 10/10/2026: tres tareas consecutivas
costaron $0.113, $0.155 y $0.000. Las dos primeras tuvieron pausas
largas (TTL expirado, caché muerta). La tercera fue inmediata (caché
activa, coste cero).

**Trabajo en ráfaga, refinado el 10/10/2026.** Dentro de una sub-fase,
OpenCode abierto: prompts de código, tests y documentación seguidos.
Al cerrar una sub-fase (commit pusheado): cerrar OpenCode. El cierre
documental de una fase es una unidad: prompts seguidos sin cerrar.
Evitar salidas accidentales al copiar. Prompts quirúrgicos con líneas
exactas. Respuestas cortas: el output cuesta cinco veces el input.
Presupuesto de referencia: $2.29 por sub-fase (medido en la Fase 3.2).
Análisis completo en `docs/audit_log.md`, entrada del 10/10/2026
(tarde).

Reglas operativas derivadas:

- **Dentro de una sub-fase: no cerrar OpenCode entre tareas.** Cada
  cierre destruye el prefijo y la siguiente tarea paga el contexto
  completo.
- **Al cerrar una sub-fase (commit pusheado, suite verde): cerrar
  OpenCode.** Al reabrir, el prefijo vuelve a ser pequeño (~5-15K
  tokens) y no arrastra contexto de sub-fases anteriores.
- **No verificar en PowerShell entre tareas.** Solo al final del
  bloque de la sub-fase, cuando ya estén hechas todas sus tareas.
- **No verificar con `git status` ni `git diff` entre tareas.**
  Acumular y verificar en bloque.
- **Si hay que hacer una pausa larga (>5 min), asumirlo.** La
  siguiente tarea pagará el prefijo completo. No es un error, es el
  comportamiento esperado.
- **Tareas en ráfaga**: 4-6 tareas seguidas sin pausa dentro de la
  sub-fase, luego verificación + commit + cierre del cliente.

**Refinamiento 11/10/2026.** La regla de ráfaga se refuerza: una sub-fase COMPLETA se manda en ráfaga (todos los prompts seguidos), y se verifica UNA sola vez al final. Enviar prompts de uno en uno con verificación intermedia rompe la caché y multiplica el coste. El desglose del Product Bill del 11/10/2026 confirma que la caché de Moonshot está operando al 93.8% de tokens servidos desde caché, y que los levers reales son: (1) respuestas cortas del modelo (output), (2) prompts quirúrgicos (input fresco), (3) no romper el TTL de 5 minutos con pausas largas. El tamaño del prefijo cacheado ya no es un lever significativo.

**Zonas grises.** No detenerse a preguntar ante ambigüedades. Tomar la decisión más conservadora, dejar un `# TODO(zona_gris): [detalle]` en el código y continuar. El humano revisará el TODO al final del bloque.

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

**Disciplina de ráfaga en la práctica (refinada 10/10/2026).** Un
bloque de trabajo típico: abrir OpenCode, hacer las tareas de la
sub-fase seguidas (prompts que el asistente estratégico diseña, el
agente aplica, no hay verificación intermedia), al terminar la
sub-fase ejecutar `git status` + `git diff --stat` +
`python -m pytest tests -q` en PowerShell, revisar el diff, commit,
push, y cerrar OpenCode. La siguiente sub-fase arranca con un cliente
nuevo y prefijo pequeño. Otras razones para cerrar y reabrir OpenCode:
un cambio en `opencode.json` que requiera recarga de configuración.

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

**Configuración correcta para OpenCode.** El archivo `opencode.json`
del proyecto debe tener:

- `"model": "moonshotai/kimi-k3"` (con "ai" al final).
- `"small_model": "moonshotai/kimi-k3"`.
- `"plugin": ["@jimmyyen/opencode-context-cache"]`.
- Sin bloque `provider.moonshot.options.setCacheKey` (no funciona en
  OpenCode 1.18.35, PR #51956).

Un typo como `"moonshot/kimi-k3"` (sin "ai") hace que OpenCode caiga a
un modelo de fallback carísimo. Esto causó el gasto anómalo del
05-06/10/2026 ($5.14 y $13.75 respectivamente).