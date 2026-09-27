# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 27/09/2026
**Propósito:** Este documento permite a una IA nueva (o a un colaborador) entender el estado de TreeGov en menos de 5 minutos, sin reconstruir contexto desde cero.

## Lectura obligatoria (en orden)

1. `AGENTS.md` — Instrucciones operativas para agentes IA
2. `.treegovrules` — Reglas de gobernanza y filosofía
3. `docs/estado_proyecto.md` — Dossier completo del proyecto
4. `docs/methodology.md` — Metodología matemática con citas
5. `docs/audit_log.md` — Bitácora cronológica (leer últimas 3 entradas)
6. `docs/roadmap.md` — Plan de fases con sub-plan de 2.3

## Estado actual del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Núcleo algorítmico (4 motores + statistics + imputación) | ✅ |
| 1 | Flujo transaccional (splitting, profiling, tree_builder, session_state) | ✅ |
| 1.2 | Evaluación OOS + poda coste-complejidad | ✅ |
| 1.3 | Validación OOT + monitoreo PSI/CSI | ✅ |
| 2.0 | GUI PySide6 (esqueleto) | ✅ |
| 2.1 | Wizard transaccional + Governance Mode | ✅ |
| 2.2 | Visor interactivo de árbol | ✅ |
| 2.3.a | Diseño estructural panel OOS/OOT | ✅ |
| 2.3.b | 23 claves i18n (paridad EN/ES) | ✅ |
| 2.3.c | Esqueleto del panel + 3 tests | ✅ |
| 2.3.d | Consumo de métricas (Kimi K3) | ⏳ Próxima |
| 2.3.e | Semáforos y visualización | ⏳ |
| 2.3.f | Tests E2E + cierre | ⏳ |
| 2.4 | Reportes + integración | ⏳ |
| 3+ | MCP, batch scoring, IFRS 9 | ⏳ |

**Suite de tests:** 161/161 PASSED

## Entorno de desarrollo

### Plataforma

- **Principal:** Windows nativo con Python 3.11.9 (`.venv/`). Verificado 27/09/2026: 161/161 tests.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 (`.venv_linux/`).
- **Motivo del respaldo:** Windows bloqueó scipy en el pasado (WDAC/Smart App Control). Actualmente funciona sin bloqueo.
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).

### Comandos por plataforma

Windows (PowerShell):

    .\.venv\Scripts\activate
    python -m pytest tests -q
    python treegov.py

WSL (bash):

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

### Herramientas

- VS Code conectado a WSL (extensión oficial de Microsoft), con terminal integrada.
- Windows Terminal con Ubuntu por defecto.
- OpenCode 1.18.31 en Windows y 1.18.32 en WSL. Modelo principal: `nvidia/moonshotai/kimi-k3` (Kimi K3 vía NVIDIA NIM). Alternativa gratuita: `Nemotron 3 Ultra Free` (OpenCode Zen).

### Configuración de OpenCode

Windows: `C:\Users\maren\.config\opencode\opencode.jsonc` y `C:\Users\maren\.local\share\opencode\auth.json`.

WSL: `~/.config/opencode/opencode.jsonc` y `~/.local/share/opencode/auth.json`.

Contenido común:

- `instructions`: AGENTS.md + .treegovrules
- `model`: nvidia/moonshotai/kimi-k3
- `permission`: git push/commit = ask, rm -rf = deny
- Plugin local del proyecto: opencode-supermemory + opencode-auto-resume (en `.opencode/opencode.json`)

## Problemas conocidos y soluciones

| Problema | Solución |
|---|---|
| **Variant de OpenCode** | Default = `max` (diseño/auditoría). Para implementación: `/variants` → `high`. Para tareas triviales: `/variants` → `low`. No persiste en `opencode.jsonc`. |
| **Cuota NVIDIA NIM agotada (429)** | Se renueva cada 24h. Alternativa gratuita: OpenCode Zen (`Nemotron 3 Ultra Free`). |
| **Modelos descontinuados** | DeepSeek V4 Pro fue retirado (14/09/2026). Verificar vigencia antes de seleccionar. |
| `Ctrl+P` no funciona en VS Code | Usar Windows Terminal para menús de OpenCode. |
| Al pegar en terminal, a veces se cuela `~` | Escribir comandos cortos a mano. |
| Al pegar en nano, el contenido se duplica | Usar Python para escribir archivos, o VS Code directo. |
| `git push` falla desde terminal WSL | Hacer push desde VS Code: `Ctrl+Shift+P` → `Git: Push`. |

## Cómo retomar el trabajo

### Windows (principal)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    opencode

### WSL (respaldo)

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

## Próximos pasos (Fase 2.3.d)

**Objetivo:** Integrar el panel OOS/OOT con las métricas del backend.

**Requisitos:**

- Consumir `OOSMetrics` (backend_v3/validation.py) — AUC, Gini, KS, Brier, BSS, HL, PR-AUC, ROC.
- Consumir `PSIReport`, `CSIReport`, `GiniDropReport` (backend_v3/stability.py) con semáforos.
- Sin importar numpy/pandas/scipy en frontend_v3 (sala limpia).
- Los semáforos (`traffic_light`, `gini_drop_alert`) se evalúan en backend.
- DTO plain-Python que cruce la frontera (dicts/tuplas de tipos nativos).

**Regla de variant:** `max` para este sub-paso (diseño + integración).

**Pendientes posteriores:** 2.3.e (semáforos visuales + QSS), 2.3.f (tests E2E + cierre).

**Ideas del experto (evaluar en 2.4 o 3):**

- Restricciones de monotonía.
- Exportación de reglas legibles (Markdown/JSON).
- Documentación automática del modelo.

## Documentos históricos

La carpeta `archive/` contiene documentos del proyecto anterior (DecisionTree_Modeler). Se conservan como referencia pero NO se deben citar ni usar como base para TreeGov. No contienen referencias a software privativo activo.

## Convenciones del proyecto

- **Comentarios y docs:** español para docs internos, inglés para código.
- **Tests:** valores verificados a mano, no autoreferencias.
- **Cada cambio de código:** actualizar `docs/audit_log.md`.
- **Cada fase cerrada:** actualizar `docs/roadmap.md` y `docs/estado_proyecto.md`.
- **Cero referencias a software privativo** (SPSS, Answer Tree, Stata, SAS) en docs activos.
- **i18n:** paridad estricta EN/ES, claves en snake_case.