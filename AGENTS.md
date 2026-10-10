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

**Regla de ráfaga.** La caché de prompt de Moonshot solo se activa si
el prefijo entre peticiones es idéntico y han pasado menos de 5
minutos desde la anterior. Trabajar en ráfagas cortas: varias tareas
seguidas sin pausas largas, luego verificar todo junto en PowerShell,
luego commit. No cerrar OpenCode entre tareas. No verificar en PS
entre cada tarea. Verificado empíricamente el 10/10/2026: tareas con
pausa >5 min cuestan ~$0.15, tareas inmediatas cuestan ~$0.00. Ver
`docs/audit_log.md` entrada del 10/10/2026 y
`docs/contexto_para_nueva_sesion.md` sección "Regla de oro de la caché
de Moonshot".

## Entorno

- **Plataforma principal:** Windows nativo.
- **Python de desarrollo y tests:** 3.11.9 (verificado 09/10/2026: 243/243 tests).
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).
- **Entorno virtual:** `.venv/` (Windows). Activar con `.\.venv\Scripts\activate`.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 y `.venv_linux/`. Se mantiene operativo por si Windows vuelve a bloquear librerías (política WDAC).

## Herramienta de desarrollo: OpenCode

- **Versión:** 1.18.35 (global vía `npm`).
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
09/10/2026 se volvió a OpenCode, ahora con la versión 1.18.35 y key
propia de Moonshot; con esta combinación (OpenCode 1.18.35 + Moonshot
directo) los problemas anteriores no se reproducen y el consumo de
tokens es sustancialmente menor.

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

## Gobernanza

Ver .treegovrules para principios completos. SplitConfig frozen, params_fingerprint único.