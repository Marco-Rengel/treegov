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

## Entorno

- **Plataforma principal:** Windows nativo.
- **Python de desarrollo y tests:** 3.11.9 (verificado 27/09/2026: 167/167 tests).
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).
- **Entorno virtual:** `.venv/` (Windows). Activar con `.\.venv\Scripts\activate`.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 y `.venv_linux/`. Se mantiene operativo por si Windows vuelve a bloquear librerías (política WDAC).

## Herramienta de desarrollo: Aider

- **Versión:** 0.86.2
- **Modelo:** `nvidia_nim/moonshotai/kimi-k3` (NVIDIA NIM)
- **Configuración local:** `.aider.conf.yml` (no versionado; ver `.gitignore`).
- **Metadata de modelos:** `~/.aider.model.metadata.json` registra
  `max_input_tokens: 1048576` y `max_output_tokens: 131072`.
- **Instalación:** global vía `pipx` (Python 3.11), fuera del `.venv/` del proyecto.

**Arranque (Windows PowerShell):**

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    $env:NVIDIA_NIM_API_KEY = "nvapi-..."   # rotar si se expone
    aider <archivo1> <archivo2>

**Reglas para Aider en este proyecto:**

- `auto-commits: false` — cada commit es decisión humana.
- Prompts quirúrgicos con referencias exactas (función, string). Evitar Grep.
- Un cambio atómico por prompt; revisar el diff antes de aplicarlo.
- Verificación obligatoria tras cada tarea: `python -m pytest tests -q` y
  `git status`.
- Migrado desde OpenCode 1.18.32 el 27/09/2026 (ver `docs/audit_log.md`).

## Gobernanza

Ver .treegovrules para principios completos. SplitConfig frozen, params_fingerprint único.