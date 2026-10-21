# AGENTS.md — TreeGov

Instrucciones para agentes de IA que trabajen en este repositorio.

## Comandos esenciales (Windows PowerShell)

    .\.venv\Scripts\activate
    python -m pytest tests -q
    python -m pytest tests/test_tree_view.py -v
    python treegov.py

    # GUI con auto-quit (headless/CI)
    $env:QT_QPA_PLATFORM="offscreen"; $env:TREEGOV_GUI_AUTOQUIT_MS="2000"; python treegov_gui.py

## Comandos esenciales (WSL bash)

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q
    python treegov.py

## Arquitectura: sala limpia

- backend_v3/ — Capa analítica pura. Cero imports de Qt/PySide6.
- frontend_v3/ — Capa de presentación. Cero lógica analítica.
- Comunicación vía backend_v3.session_state.Session.

## Reglas de caja blanca

Prohibido importar: sklearn, scikit-learn, statsmodels, xgboost, lightgbm, catboost.
Bloqueadas por backend_v3/import_guard.py. Toda fórmula con cita bibliográfica.

## Documentación obligatoria

Actualizar docs/audit_log.md al modificar código (formato: fecha, estado, artefactos, hallazgos, tests).

Verificación obligatoria tras cada tarea de agente: `python -m pytest tests -q`
y `git status`. No confiar en la notificación de éxito del agente sin esa
doble verificación.
Los line endings del repo están normalizados vía `.gitattributes`
(ver commit 7040046). No tocar esa configuración sin motivo documentado.

Cuando una sub-fase cierra (commit pusheado, suite verde), la
actualización de `docs/audit_log.md`, `docs/roadmap.md`,
`docs/estado_proyecto.md` y los documentos de contexto se hace EN EL
MISMO BLOQUE de trabajo, nunca en una sesión aparte. Aplazar la
documentación desincroniza los documentos de contexto respecto al
código real y fuerza reconstrucciones costosas al abrir un chat nuevo.
Excepciones: solo 504/timeout del proveedor de IA (se documenta al
volver), o cambio trivial de 1 línea consolidado en la entrada de
bloque. Ver `docs/roadmap.md` sección "Recorded architectural
decisions: Phase closure documentation: never deferred".

**Checklist de cierre ampliado a 8 documentos (actualizado 20/10/2026).**
Al cerrar una sub-fase, la sincronización documental exige:
1. `docs/audit_log.md`: entrada de cierre.
2. `docs/roadmap.md`: estado de la fase y sección narrativa.
3. `docs/estado_proyecto.md`: conteo de tests real Y bloque narrativo de la fase cerrada.
4. `docs/contexto_para_nueva_sesion.md`: próximo paso.
5. `docs/prompt_para_asistente.md`: herramienta activa y estado.
6. `README.md` / `README.es.md`: versión, conteo de tests Y fila en la tabla de fases.
7. `docs/api.md`: superficie pública de la API.
8. `docs/design_decisions.md`: nueva entrada si el cambio introdujo un nuevo default o alteró un contrato de API.
Si alguno de los 8 no refleja el estado real, la sub-fase NO se considera cerrada. Motivo: el cierre de la Fase 3.8 el 19/10/2026 omitió la fila en el README, el bloque narrativo en `estado_proyecto.md` y la entrada en `design_decisions.md`, forzando un bloque de corrección post-cierre el 20/10/2026.

**Protocolo PyPI (Actualizado 20/10/2026).** PyPI congela el README al subir. Para evitar inflación de versiones por cosmética:
- **Cambios materiales** (código, defaults, contratos, citas regulatorias): publicar nueva versión inmediatamente.
- **Cambios cosméticos** (fechas en diagramas, typos, tablas de estado, narrativa): NO publicar nueva versión. Esperar a la próxima release material y documentar la desincronización en `docs/roadmap.md` (sección Deferred).

**Regla de ráfaga (refinada el 10/10/2026).** Dentro de una sub-fase:
OpenCode abierto, los prompts de código, tests y documentación van
seguidos, sin cerrar el cliente. Al cerrar una sub-fase (commit
pusheado y suite verde): cerrar OpenCode. Al reabrir, el prefijo
vuelve a ser pequeño (entre cinco y quince mil tokens) y no arrastra
el contexto acumulado de sub-fases anteriores. El cierre documental
de una fase se trata como una unidad: los prompts de documentación
van seguidos sin cerrar entre ellos. Evitar salidas accidentales al
copiar un prompt. Prompts quirúrgicos: nombrar líneas exactas cuando
se edita código. Instrucciones de respuesta corta: el output del
modelo cuesta cinco veces más que el input nuevo. Presupuesto por
sub-fase de referencia: $2.29 (medido en la Fase 3.2). Si una
sub-fase futura excede $3, diagnosticar. Análisis completo en
`docs/audit_log.md`, entrada del 10/10/2026 (tarde).

## Entorno

- **Plataforma principal:** Windows nativo.
- **Python de desarrollo y tests:** 3.11.9 (verificado 09/10/2026: 243/243 tests).
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).
- **Entorno virtual:** `.venv/` (Windows). Activar con `.\.venv\Scripts\activate`.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 y `.venv_linux/`. Se mantiene operativo por si Windows vuelve a bloquear librerías (política WDAC).

**Herramientas CLI: SIEMPRE vía pipx, nunca en el .venv del proyecto.** Las herramientas de desarrollo (Aider, build, twine, linters, formatters) NO se instalan con pip dentro del .venv del proyecto. Se instalan globalmente con pipx, que las aísla en su propio entorno. Motivo: instalar herramientas CLI dentro del .venv degrada las versiones de las librerías compartidas (numpy, scipy, packaging, rich) y rompe la compatibilidad verificada del proyecto. Esto ya ocurrió dos veces: el 27/09/2026 (Aider bajó numpy 2.4.6 → 1.26.4 y scipy 1.17.1 → 1.15.3) y el 12/10/2026 (build/twine subieron packaging 26.0 → 26.3 y rich 14.3.2 → 15.0.0, rompiendo los pins de Aider). Verificación obligatoria tras instalar cualquier herramienta CLI: ejecutar pip show <tool> y confirmar que Location apunta a C:\Users\maren\AppData\Local\pipx\pipx\venvs\..., no al .venv del proyecto.

**UTF-8 en PowerShell (lección 18/10/2026).** Al verificar archivos con caracteres no-ASCII (acentos, comillas tipográficas, `§`, `≥`, guiones largos), `git diff` en la consola de PowerShell puede mostrar mojibake aunque el archivo en disco esté correcto. Motivo: PowerShell decodifica stdout con un codepage no UTF-8 y la corrupción ocurre en la tubería, no en el archivo. `git diff | Out-File -Encoding utf8` NO arregla el problema, porque el daño ocurre antes del `Out-File`.

Verificación fiable (una de dos):

1. Script Python que lee los archivos con `io.open(encoding="utf-8")` y comprueba contenido y puntos de código.
2. `git --no-pager diff --output=diff_utf8.txt <archivos>`, que escribe bytes directamente a disco sin pasar por la tubería de strings de PowerShell. Abrir `diff_utf8.txt` en Notepad o VS Code para revisión visual.

## Herramienta de desarrollo: OpenCode

- **Versión:** 1.19.0 (global vía `npm`).
- **Modelo:** `moonshotai/kimi-k3` (Kimi K3).
- **Autenticación:** `opencode auth login` con provider `Moonshot AI`
  (internacional, endpoint `https://api.moonshot.ai/v1`). La key es
  propia de Moonshot, NO se pasa por NVIDIA NIM.
- **Configuración del proyecto:** `opencode.json` en la raíz
  (versionado), con `model`, `small_model`, `plugin`
  (`@jimmyyen/opencode-context-cache`), `autoupdate: false`,
  `share: "disabled"`.
- **Sin variables de entorno:** OpenCode gestiona la key internamente
  en `~/.local/share/opencode/auth.json`.

**Arranque (Windows PowerShell):**

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    opencode

**Reglas para OpenCode en este proyecto:**

- Un prompt = un archivo (por claridad de diffs y auditoría).
- Prosa sin código literal (recomendado, no obligatorio).
- Hasta ~150 líneas de prosa por prompt.
- Cada commit es decisión humana (sin auto-commits).
- Verificación obligatoria tras cada tarea: `python -m pytest tests -q`,
  `git status` y `git diff` del archivo tocado.

**Nota histórica:** OpenCode se usó al inicio con NVIDIA NIM (key
gratuita) y dio problemas de tool calls. Aider lo sustituyó el
27/09/2026. El 03/10/2026 se migró a Moonshot directo con Aider. El
09/10/2026 se volvió a OpenCode, ahora con la versión 1.19.0 y key
propia de Moonshot; con esta combinación (OpenCode 1.19.0 + Moonshot
directo) los problemas anteriores no se reproducen y el consumo de
tokens es sustancialmente menor. Actualizado a 1.19.0 el 11/10/2026.

### Herramienta de respaldo — Aider 0.86.2

Se usa solo si OpenCode falla en algún caso concreto. No desinstalar.

- **Versión:** 0.86.2 (global vía `pipx`, Python 3.11.9).
- **Modelo:** `moonshot/kimi-k3` (endpoint `https://api.moonshot.ai/v1`).
- **Configuración local:** `.aider.conf.yml` (no versionado; ver `.gitignore`).
- **Plantilla versionada:** `.aider.conf.example.yml`.
- **Metadata de modelos (en el home del usuario):**
  - `~/.aider.model.metadata.json` — contexto (1M tokens) y costes reales
    ($3/M input, $15/M output).
  - `~/.aider.model.settings.yml` — comportamiento por modelo
    (`use_temperature: false` y `edit_format: whole` para Kimi K3).
- **Variable de entorno:** `$env:MOONSHOT_API_KEY`.

**Arranque del respaldo (Windows PowerShell):**

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    $key = Read-Host "Pega tu Moonshot API key" -AsSecureString
    $env:MOONSHOT_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
    Remove-Variable key
    aider <archivo1> <archivo2>

### Configuración correcta del modelo

El archivo `opencode.json` del proyecto debe tener
`"model": "moonshotai/kimi-k3"` y `"small_model": "moonshotai/kimi-k3"`
(con "ai" al final). Un typo como `"moonshot"` hace que OpenCode caiga
silenciosamente a un modelo de fallback más caro. Este fue el origen
del gasto anómalo del 05-06/10/2026 ($5.14 y $13.75 en Model
Inference respectivamente). Verificado: los logs de OpenCode mostraban
"Model not found: moonshot/kimi-k3. Did you mean: moonshotai,
moonshotai-cn?".

### Plugin de caché

El plugin `@jimmyyen/opencode-context-cache` debe estar en el array
`plugin` del `opencode.json`. Sin él, la caché de prompt de Moonshot
no se activa correctamente. Con él, el coste por tarea dentro de la
ventana de 5 minutos es prácticamente cero.

### Plugins fantasma eliminados

La carpeta `.opencode/` del proyecto fue eliminada el 10/10/2026.
Contenía un archivo `opencode.json` con dos plugins problemáticos:
`opencode-supermemory` (roto) y `opencode-auto-resume`. No recrear esa
carpeta sin justificación. Si algún día se necesita un plugin global,
usar la configuración global en `~/.config/opencode/`.

### Nivel de razonamiento del agente (política desde 11/10/2026)

OpenCode permite elegir el nivel de razonamiento del modelo con el comando `/variants`. La política del proyecto es:

- **`high`** (default): documentación pura, ediciones quirúrgicas simples (< 20 líneas), actualizaciones de comentarios y docstrings.
- **`max`** (obligatorio): cambios de firma de funciones públicas, sub-fases con múltiples archivos, refactors estructurales, depuración de bugs.
- **`low`**: NO es válido para trabajo técnico.

El criterio central: **si el cambio puede romper consumidores en cascada, `max`**.

Evidencia: durante la Fase 3.3.d, la configuración por defecto de OpenCode quedó en `low` tras la actualización a 1.19.0, y produjo 15 fallos evitables en la suite. Al subir a `max`, los errores se detectan antes de escribir el código. El coste por prompt sube de ~$0.15 a ~$0.37, pero el ahorro en correcciones lo compensa.

Verificación: la cabecera del chat de OpenCode muestra el nivel activo (p. ej. `Build · Kimi K3 Moonshot AI · max`).

## Gobernanza

Ver .treegovrules para principios completos. SplitConfig frozen, params_fingerprint único.