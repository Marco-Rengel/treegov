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

## Entorno

- **Plataforma principal:** Windows nativo.
- **Python de desarrollo y tests:** 3.11.9 (verificado 03/10/2026: 199/199 tests).
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).
- **Entorno virtual:** `.venv/` (Windows). Activar con `.\.venv\Scripts\activate`.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 y `.venv_linux/`. Se mantiene operativo por si Windows vuelve a bloquear librerías (política WDAC).

## Herramienta de desarrollo: Aider

- **Versión:** 0.86.2 (global vía `pipx`, Python 3.11.9).
- **Modelo:** `moonshot/kimi-k3` (Moonshot AI directo, plataforma
  internacional).
- **Endpoint:** `https://api.moonshot.ai/v1` (LiteLLM lo conoce por defecto).
- **Configuración local:** `.aider.conf.yml` (no versionado; ver `.gitignore`).
- **Plantilla versionada:** `.aider.conf.example.yml`.
- **Metadata de modelos (en el home del usuario):**
  - `~/.aider.model.metadata.json` — contexto (1M tokens) y costes reales
    ($3/M input, $15/M output).
  - `~/.aider.model.settings.yml` — comportamiento por modelo
    (`use_temperature: false` y `edit_format: whole` para Kimi K3).
- **Variable de entorno:** `$env:MOONSHOT_API_KEY`.

**Arranque (Windows PowerShell):**

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    $key = Read-Host "Pega tu Moonshot API key" -AsSecureString
    $env:MOONSHOT_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
    Remove-Variable key
    aider <archivo1> <archivo2>

**Reglas para Aider en este proyecto:**

- `auto-commits: false` — cada commit es decisión humana.
- Un cambio atómico por prompt; revisar el diff antes de aplicarlo.
- Verificación obligatoria tras cada tarea: `python -m pytest tests -q`,
  `git status` y `git diff` del archivo tocado.
- Migrado de OpenCode 1.18.32 el 27/09/2026 y de NVIDIA NIM el 03/10/2026
  (ver `docs/audit_log.md`).
- **Reglas de prompts (suavizadas respecto a NIM):**
  - Un prompt = un archivo (se mantiene por claridad de diffs y auditoría).
  - Prosa sin código literal (recomendado, no obligatorio).
  - Hasta ~150 líneas de prosa por prompt (antes ~30-100 con NIM).
  - Cambios multi-bloque dentro del mismo archivo: permitido.
  - Si Aider falla 2-3 veces seguidas sobre el mismo archivo (conversa en lugar de aplicar), hacer la edición manual en VS Code y documentar la excepción en el audit_log (regla 29/09/2026).

## Gobernanza

Ver .treegovrules para principios completos. SplitConfig frozen, params_fingerprint único.