# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 29/09/2026
**Propósito:** Este documento permite a una IA nueva (o a un colaborador) entender el estado de TreeGov en menos de 5 minutos, sin reconstruir contexto desde cero.

## Lectura obligatoria (en orden)

1. `AGENTS.md` — Instrucciones operativas para agentes IA
2. `.treegovrules` — Reglas de gobernanza y filosofía
3. `docs/estado_proyecto.md` — Dossier completo del proyecto
4. `docs/methodology.md` — Metodología matemática con citas
5. `docs/audit_log.md` — Bitácora cronológica (leer últimas 3 entradas)
6. `docs/roadmap.md` — Plan de fases con sub-plan de 2.3
7. `docs/prompt_para_asistente.md` — Brief para asistentes IA nuevos

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
| 2.3.d | Backend de reporting (reporting.py + Session + tests) | ✅ |
| 2.3.e.1 | Normalización de semáforos (alfabeto en inglés) | ✅ |
| 2.3.e.2 | i18n: renombrar claves y añadir nuevas | ✅ |
| 2.3.e.3 | Tokens QSS semánticos | ✅ |
| 2.3.e.4 | MetricsPanel funcional | ⏳ Próxima |
| 2.3.e.5 | Cableado MainWindow ↔ MetricsPanel | ⏳ |
| 2.3.f | Tests E2E + cierre | ⏳ |
| 2.4 | Reportes + integración | ⏳ |
| 3+ | MCP, batch scoring, IFRS 9 | ⏳ |

**Suite de tests:** 167/167 PASSED

## Entorno de desarrollo

### Plataforma

- **Principal:** Windows nativo con Python 3.11.9 (`.venv/`). Verificado 27/09/2026: 167/167 tests.
- **Librerías:** numpy 1.26.4, scipy 1.15.3, pandas 3.0.6, PySide6 6.11.2 (degradadas por instalación de Aider; ver audit_log 27/09/2026).
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
- **Aider 0.86.2** (reemplaza a OpenCode desde el 27/09/2026).
- **Modelo:** `nvidia_nim/moonshotai/kimi-k3` (NVIDIA NIM).
- **Configuración local:** `.aider.conf.yml` (no versionado).
- **Metadata de modelos:** `~/.aider.model.metadata.json`.

### Configuración de Aider

- **API key:** `$env:NVIDIA_NIM_API_KEY` exportada por sesión (PowerShell).
- **Metadata de Kimi K3:** `C:\Users\maren\.aider.model.metadata.json`.
- **Configuración de proyecto:** `.aider.conf.yml` (ignorado por git).
- **Flags clave:** `auto-commits: false`, `auto-lint: false`, `auto-test: false`.

## Problemas conocidos y soluciones

| Problema | Solución |
|---|---|
| **Bug OpenCode + Gemini** | `Requests ending with a model turn are not supported` bloquea escritura tras exploración. **Migrado a Aider.** Ver `audit_log.md`. |
| **Context window de Kimi K3** | Aider no conoce el modelo; requiere `~/.aider.model.metadata.json`. Ver `audit_log.md` 27/09/2026. |
| **API key con prefijo duplicado** | Verificar `$env:NVIDIA_NIM_API_KEY.Substring(0, 20)` empieza con `nvapi-` (una sola vez). |
| **BOM en archivos JSON creados con PowerShell** | Usar `[System.IO.File]::WriteAllText(..., [System.Text.UTF8Encoding]::new($false))`. |
| **Modelos descontinuados** | DeepSeek V4 Pro retirado (14/09/2026). |
| **Privacidad** | No enviar datos bancarios reales ni credenciales a APIs gratuitas. |
| **Pegado en terminal** | A veces duplica contenido o deja caracteres colgando. Escribir comandos cortos a mano. |
| `git push` desde WSL | Hacer push desde Windows nativo (PowerShell) o VS Code. |
| **Placeholder de API key** | Si pegas `$env:NVIDIA_NIM_API_KEY = "nvapi-..."` literal, Aider devuelve 403. Verificar con `.Length` (~70 caracteres) y `.Substring(0, 10)` sin duplicar `nvapi-`. |

## Cómo retomar el trabajo

### Windows (principal)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    $env:NVIDIA_NIM_API_KEY = "nvapi-..."
    aider

### WSL (respaldo)

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

## Próximos pasos (Fase 2.3.e.4)

**Objetivo:** que `MetricsPanel` consuma el DTO de `Session.get_oos_oot_report()`
y renderice las métricas OOS/OOT con badges de estado.

**Requisitos:**

- `MetricsPanel.set_report(dto: dict | None) -> None` que reciba el DTO y
  lo guarde.
- Construir la UI del panel: secciones OOS y OOT con etiquetas y valores.
- Renderizar badges de estado usando `QLabel` con `setProperty("status", ...)`
  y los selectores QSS de `styles.qss` (`ok`, `warn`, `crit`, `unknown`).
- Mapear los strings del alfabeto backend a la propiedad `status`:
  - `"STABLE"` → `ok`
  - `"MODERATE"` → `warn`
  - `"UNSTABLE"` → `crit`
  - `"CRITICAL"` → `crit`
  - `"WARNING"` → `warn`
  - `"NONE"` → `ok`
  - `"UNDETERMINED"` → `unknown`
- Consumir las claves i18n de estado (`tr(f"status_{...}")`) para el texto
  visible.
- Sin importar numpy/pandas/scipy (sala limpia).

**Herramienta:** Aider + Kimi K3 vía NVIDIA NIM.

**Sub-pasos posteriores:**
- 2.3.e.5 Cableado MainWindow ↔ MetricsPanel
- 2.3.f Tests E2E + cierre
- 2.4 Reportes + integración

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
- **Verificación manual obligatoria** tras cada tarea de Aider: `python -m pytest tests -q`, `git status`, `git diff` del archivo tocado.