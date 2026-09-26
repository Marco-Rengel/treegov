# AGENTS.md — TreeGov

Instrucciones para agentes de IA que trabajen en este repositorio.

## Comandos esenciales

    source .venv_linux/bin/activate
    python -m pytest tests -q
    python -m pytest tests/test_tree_view.py -v
    python treegov.py
    QT_QPA_PLATFORM=offscreen TREEGOV_GUI_AUTOQUIT_MS=2000 python treegov_gui.py

## Arquitectura: sala limpia

- backend_v3/ — Capa analítica pura. Cero imports de Qt/PySide6.
- frontend_v3/ — Capa de presentación. Cero lógica analítica.
- Comunicación vía backend_v3.session_state.Session.

## Reglas de caja blanca

Prohibido importar: sklearn, scikit-learn, statsmodels, xgboost, lightgbm, catboost.
Bloqueadas por backend_v3/import_guard.py. Toda fórmula con cita bibliográfica.

## Documentación obligatoria

Actualizar docs/audit_log.md al modificar código (formato: fecha, estado, artefactos, hallazgos, tests).

## Entorno

WSL2 (Ubuntu) con Python 3.14.4. Windows nativo NO se usa (bloquea DLLs de scipy).
Entorno virtual: .venv_linux/ (NO .venv/).

## Gobernanza

Ver .treegovrules para principios completos. SplitConfig frozen, params_fingerprint único.
