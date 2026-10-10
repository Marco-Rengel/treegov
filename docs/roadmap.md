# TreeGov Roadmap

**Legend:** ✅ Completed · 🟡 In progress · ⏳ Planned

## Completed

- ✅ **Phase 0** (algorithmic core): 4 engines + statistics + types +
  import_guard + log_config.
- ✅ **Phase 1** (transactional flow): splitting + profiling + tree_builder +
  session_state.
- ✅ **Phase 1.2** (OOS evaluation + pruning): validation + pruning.
  - Test suite: 107/107.
- ✅ **Phase 1.3** (OOT + stability): stability.py + extensions to
  session_state.py.
  - Test suite: 119/119.
- ✅ **Phase 2.0** (GUI skeleton): PySide6 QMainWindow (menus, 3-panel
  splitter, status bar), QSS light/dark themes, bilingual EN/ES i18n via
  plain-Python dictionary with live retranslate.
  - Test suite: 128/128.
- ✅ **Phase 2.1** (transactional wizard): 4-step QWizard (engine,
  predictors/target, validation scheme, MRM governance) feeding Session.
  Governance Mode (Banking/Research) added: Banking is the default;
  Research disables Jeffreys + PD Floor for non-banking domains (health,
  social sciences). Backend gained Session.describe_dataset() /
  fix_spec(predictors=...) / train(engine by name) /
  reset_to_data_loaded().
  - Test suite: 148/148.
- ✅ **Phase 2.2** (interactive tree viewer): QGraphicsView render with
  deterministic Reingold-Tilford layout, idempotent zoom (Ctrl + +/-),
  exclusive node selection, live retranslation, theme recolor.
  - Test suite: 158/158.

## Upcoming phases


### ✅ Phase 2.3 — OOS/OOT metrics panel
**Priority: HIGH** · **Cerrada el 29/09/2026**

**Métricas requeridas:**
- Gini, KS, HL, Brier, ROC + AUC, PR-AUC (`backend_v3/validation.py`)
- PSI, CSI, Gini Drop con semáforos Basel/EBA (`backend_v3/stability.py`)
- Mnemonics de teclado ("&") para menús

**Metodología de trabajo (actualizada 03/10/2026):**

La Fase 2.3 se dividió en sub-pasos cortos. Todas las sub-fases se
ejecutaron con **Aider 0.86.2 + Kimi K3 con tool calls** (migrado desde
OpenCode el 27/09/2026 y a Moonshot AI directo el 03/10/2026; ver
`docs/audit_log.md`).

| Sub-paso | Estado | Alcance |
|---|---|---|
| 2.3.a Diseño estructural | ✅ | Dónde encaja el panel; archivos a crear/modificar |
| 2.3.b Claves i18n | ✅ | 23 claves EN/ES con paridad estricta |
| 2.3.c Esqueleto del panel | ✅ | Clase widget + 3 tests de construcción |
| 2.3.d Backend de reporting | ✅ | `backend_v3/reporting.py` + `Session.get_oos_oot_report()` + 6 tests |
| 2.3.e.1 Normalización de semáforos | ✅ | Alfabeto backend en inglés (`STABLE`/`MODERATE`/`UNSTABLE`/`UNDETERMINED`/`CRITICAL`/`WARNING`/`NONE`) |
| 2.3.e.2 Claves i18n por estado | ✅ | Renombrado `status_green/yellow/red` → `status_stable/moderate/unstable` + 4 claves nuevas |
| 2.3.e.3 Tokens QSS semánticos | ✅ | 4 tokens (`STATUS_OK/WARN/CRIT/UNKNOWN`) en ambas paletas + 4 selectores QSS |
| 2.3.e.4 MetricsPanel funcional | ✅ | Consume el DTO + badges con QSS + 6 tests nuevos |
| 2.3.e.5 Cableado MainWindow ↔ MetricsPanel | ✅ | Handlers de menú + refresco automático del panel |
| 2.3.f Tests E2E + cierre | ✅ | 5 tests E2E nuevos (178/178); Fase 2.3 completa |
| 2.3 ✅ | OOS/OOT metrics panel — **cerrada** | La Fase 2.3 completa (a-f) está operativa end-to-end |

**Regla de proveedor:**
- **Aider 0.86.2 + Kimi K3 vía Moonshot AI directo**: implementación,
  edición de archivos, tests, refactor, documentación.
- **Instalación:** global vía `pipx` con Python 3.11.9 (fuera del `.venv/`).
- **Histórico:** hasta el 03/10/2026 se usó NVIDIA NIM (free tier); se
  migró a Moonshot AI directo por inestabilidad de NIM (504 recurrentes).
  Ver `docs/audit_log.md` entradas del 03/10/2026.

Cada sub-paso se audita antes de pasar al siguiente. Verificación manual
obligatoria (`python -m pytest tests -q`, `git status`, `git diff` del
archivo tocado) tras cada tarea de Aider.

### ✅ Phase 2.4 — Reports + integration
**Priority: MEDIUM** · **Cerrada el 03/10/2026**

**Objetivo:** panel de reportes analíticos con gains table, matriz de
clasificación y exportación HTML autocontenido.

**Sub-pasos:**

| Sub-paso | Estado | Alcance |
|---|---|---|
| 2.4.a Diseño estructural | ✅ | Pestaña Reports + `reports_panel.py` (placeholder) + 2 claves i18n + tests ajustados |
| 2.4.b Backend de reportes | ✅ (03/10/2026) | `GainsTable` + `ClassificationMatrix` en `backend_v3/reporting.py`; 5 tests con valores verificados a mano |
| 2.4.c.1 Backend de Session | ✅ (03/10/2026) | `get_gains_table` + `get_classification_matrix` en `Session`; 5 tests |
| 2.4.c.2.a Panel funcional | ✅ (03/10/2026) | `reports_panel.py` + 65 claves i18n; sin Export HTML ni cableado |
| 2.4.c.2.b Cableado MainWindow | ✅ (03/10/2026) | 4 señales conectadas + refresh tras entrenar/evaluar/cargar OOT |
| 2.4.c.2.c.1 Export HTML | ✅ (03/10/2026) | QDialog + QTextBrowser + save-as |
| 2.4.c.2.c.2 Limpieza i18n | ✅ (03/10/2026) | 14 claves huérfanas eliminadas |
| 2.4.c.2.c.3 Tests del panel | ✅ (03/10/2026) | 7 tests unitarios en `tests/test_reports_panel.py` |
| 2.4.d Tests E2E + cierre | ✅ (03/10/2026) | 4 tests E2E en `test_e2e_reports.py`; screenshot diferido a 2.4.e |

**Diseño acordado (30/09/2026):**

**`GainsTable`** — salida resumen del modelo:
- `by="leaf"` (default): una fila por hoja, ordenadas por PD ascendente
  (mejor primero).
- `by="bucket", n_buckets=10`: agrupa filas en N buckets ordenados por PD.
  Parametrizable (deciles, veintiles, o N mayor para bases grandes).
- `tie="preserve"` (default, determinista): empates de PD van juntos al
  mismo bucket. `tie="random"` con `seed` disponible como opción explícita
  — nunca default, porque viola el principio de determinismo.
- Orden default: PD ascendente (mejor primero, coherente con convención
  de burós).
- Columnas: score/leaf, total (Int/Cum/Decum), good (Int/Cum/Decum),
  bad (Int/Cum/Decum), bad_rate (Int/Cum/Decum), lift acumulado.
- Totales calculados: KS, ROC (AUC), Gini = 2·AUC−1.
- Nota al pie: `n_excluded` (filas sin PD asignado por `unseen_policy`).

**`ClassificationMatrix`** — matriz 2×2:
- `threshold=0.5` por defecto.
- Parametrizable en la UI (input numérico).
- Extensible a umbral óptimo por costo (IFRS 9, §8.6 de methodology).
- Métricas: TP, TN, FP, FN, precisión, recall, F1, tasa de malos
  capturada.

**UI (`reports_panel.py`):**
- Pestaña nueva después de "OOS/OOT".
- Toggle: partición (OOS / train / OOT).
- Toggle: vista (por hoja / por bucket con N configurable).
- Tabla Qt con `setSortingEnabled(True)`: headers clicables permiten
  reordenar visualmente sin afectar los cálculos Cum/Decum (que se
  computan en backend con el orden natural).
- Botón "Export HTML": QTextBrowser renderiza HTML autocontenido (sin
  assets externos). Portable por email y archivable.
- Sala limpia: cero numpy/pandas/scipy.

**Deudas documentadas para fases futuras:**

- **Fase 3.x — Soporte multiclase en el flujo del árbol.** Los motores
  (CHAID, CRT) ya lo soportan; `TreeBuilder`, `TreeNode.pd_final` y
  `Session.fix_spec` están restringidos a binario. Requeriría cambiar
  el tipo de `pd_final` a vector de K clases. Aplicable a salud,
  ciencias sociales (referente: SPSS).
- **Fase 3.x — Ponderación por muestra.** Para replicar flujo de buró
  (Equifax, Experian) donde la muestra está sesgada y se reajusta por
  pesos. No aplica a TreeGov hoy (datasets completos).
- **Fase 3.x — Categorías adicionales.** `Indet`, `Insufficient`,
  `No Perf` como metadatos de población (no entran al modelo). Relevante
  cuando se integre con sistemas de buró.

### ✅ Phase 3.1 — Multiclase (target + TreeNode + TreeBuilder + wizard + MetricsPanel)
**Priority: HIGH** · **Cerrada el 09/10/2026**

**Motivación.** Extiende la pipeline de construcción de árboles a targets
con K ≥ 2 clases (antes solo binario). Cubre la capa profunda
(TreeNode/TreeModel/TreeBuilder), la sesión (fix_spec/SessionState), los
consumidores downstream (validation/reporting/stability con bloqueo
explícito hasta Fase 3.5), el wizard multiclase y las alertas
post-entrenamiento en MetricsPanel (badge de Gini negativo + botón de
reversión).

**Sub-pasos:**

| Sub-paso | Estado | Alcance |
|---|---|---|
| 3.1.a | ✅ | TreeNode/TreeModel con tuple fields (pd_final/pd_jeffreys/n_events) + class_labels + TreeBuilder.target_class |
| 3.1.b | ✅ | Jeffreys multivariante (k_c + 0.5) / (n + K*0.5) + pd_floor renormalizado + reordenamiento canónico (target_class en índice 0) |
| 3.1.c | ✅ | Session.fix_spec + SessionState con target_class/class_labels obligatorios + bloqueo C&RT/QUEST con K>2 |
| 3.1.d | ✅ | predict_pd devuelve 2D (n_rows, K) + bloqueos K>2 en evaluate_oos/evaluate_oot/get_gains_table/get_classification_matrix |
| 3.1.e | ✅ | Wizard multiclase: tabla de clases (label/valor/count/radio de interés) + warning amber si se elige la clase mayoritaria |
| 3.1.f | ✅ | MetricsPanel: badge rojo si gini<0 + botón de reversión de clase + handler de reentrenamiento en MainWindow |

**Invariante no negociable.** Para K=2 con target_class=1 y labels
estándar, el modelo producido es numéricamente idéntico al pre-3.1.
Verificado por `test_multiclass_binary_parity`.

**Alcance.** CHAID y CHAID_EXHAUSTIVE son los únicos motores que admiten
K>2 en 3.1; C&RT y QUEST se abren en Fase 3.4. Las métricas y reportes
siguen binarios hasta Fase 3.5.

**Suite: 243/243 PASSED.**

**Referencias:** `docs/3.1_design_multiclass.md`,
`docs/design_decisions.md` §5.2, §5.3, §5.7, §12.1,
`docs/audit_log.md` entradas del 09/10/2026.

### ⏳ Phase 3 — Advanced analytics + documentation closure
**Priority: HIGH**

**Objetivo.** Cerrar la "zona gris" de decisiones implícitas acumuladas en
Fases 0-2, y extender la analítica del motor para cubrir los casos de uso
reales de crédito (muestras sesgadas, categorías Indet/No Perf, multiclase)
y no-crédito (biología, ciencias sociales).

**Sub-fases:**

| Sub-fase | Alcance | Prioridad |
|---|---|---|
| 3.0 | ✅ Documentación + parámetros canónicos vs TreeGov (design_decisions.md + 4 parámetros) | Completada 04/10/2026 |
| 3.1 | ✅ Multiclase en el árbol (target + TreeNode + TreeBuilder + wizard + MetricsPanel) | Completada 09/10/2026 |
| 3.2 | Ponderación por muestra (transversal al backend) | Alta |
| 3.3 | Categorías Indet / Insufficient / No Perf | Alta |
| 3.4 | CRT y QUEST multiclase | Media |
| 3.5 | Reportes adaptados (multiclase + ponderación) | Media |
| 3.6 | Validación con datasets públicos (German Credit, UCI) | Alta |
| 3.6.b | Modo no-bancario (terminología + ejemplos + docs) | Media |
| 3.7 | Cierre Fase 3 + v1.0.0 estable | Alta |

**Desglose de la Fase 3.2:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.2.a | statistics.py ponderado (f_oneway, brown_forsythe) | ✅ 10/10/2026 |
| 3.2.b | CHAID con conteos ponderados (χ²/F + merging + Cochran) | ✅ 10/10/2026 |
| 3.2.c | C&RT con Gini/varianza ponderada + surrogates | ✅ 10/10/2026 |
| 3.2.d | QUEST con Stage 1 + QDA ponderados | ✅ 10/10/2026 |
| 3.2.e | TreeBuilder (weights + min_child_weight + fingerprint) | ✅ 10/10/2026 |
| 3.2.f | Session (fix_spec + partition + train + reset) | ⏳ |
| 3.2.g | validation y reporting ponderados | ⏳ |
| 3.2.h | stability ponderado + wizard + E2E + cierre | ⏳ |

**Nota histórica.** El roadmap original de Fase 3 agrupaba "reportes
analíticos + MCP + export SQL/Python". Esa agrupación era demasiado
amplia: mezclaba analítica avanzada (necesaria para uso real en banca) con
capa de interoperabilidad (MCP), con export a producción. La redefinición
del 04/10/2026 separa esas familias:

- **Fase 3 (esta):** analítica avanzada + documentación + validación.
- **Fase 4:** reportes avanzados + export SQL/Python.
- **Fase 5:** capa MCP.
- **Fase 6:** batch scoring + champion-challenger.
- **Fase 7:** IFRS 9 / ECL.

**Deudas diferidas a fases futuras (documentadas):**
- Fase 3.x — Screenshot automatizado de la GUI (requiere xvfb o runner
  gráfico).
- Fase 2.1.b — CV scheme + guardrail runtime de imports backend.

### ⏳ Phase 4 — Advanced reports + export
**Priority: MEDIUM**

- Dual export: nested SQL + pure Python.
- Rule export (Markdown / JSON).
- Automatic model documentation.

### ⏳ Phase 5 — MCP layer
**Priority: MEDIUM**

- MCP (Model Context Protocol) layer for consumption from LLM agents.
  Headless backend as the base; MCP as an adapter (does not replace
  the GUI).

### ⏳ Phase 6 — Batch scoring and production
**Priority: MEDIUM**

- Apply the tree to the full portfolio.
- Champion-challenger: compare engines and versions.

### ⏳ Phase 7 — IFRS 9 / ECL
**Priority: LOW (depends on integration with banking systems)**

- PD per segment (tree leaf).
- Staging (Stage 1/2/3).
- ECL computation: PD × LGD × EAD.

## Deferred (no blocking current work)

### ⏳ Phase 2.1.b — Hardening extras
**Priority: LOW (deferred)**

- Cross-validation scheme (Step 3 combo placeholder already in place).
- Runtime backend-import guardrail in the GUI process (deferred from
  Phase 2.0; the AST smoke check only covers numpy/pandas/scipy).

**Motivo del aplazamiento:** ninguna de estas dos mejoras es bloqueante
para las fases 2.4, 3, 4 o 5. Se retomarán si aparece una necesidad
concreta (por ejemplo, auditoría externa que requiera CV formal, o
incidente que exponga la ausencia del guardrail runtime).

### ⏳ E2E test fixture: target con señal real
**Priority: LOW (deferred)**

El helper `_make_csv` de `tests/test_e2e_mainwindow.py` y
`tests/test_e2e_reports.py` genera un target con relación aleatoria a los
predictores, por lo que el Gini OOS es ruido de pequeña magnitud. Esto
hace que los tests E2E verifiquen el plumbing (flujo, refresco, señales,
transiciones) pero no la analítica real. Mejora pendiente: reemplazar el
fixture por uno con señal real (por ejemplo, `y = 1_{edad >= 40}` con
`edad` como predictor real), conservando la misma forma del CSV
(columnas edad/seg/ratio/default) para no romper los tests existentes.
Se difiere porque ningún test depende hoy de que el Gini sea
significativo.

### ✅ OpenCode token consumption anomaly — RESOLVED (10/10/2026)
**Priority: LOW (resolved, no longer blocking).**

**Causa raíz.** El archivo `opencode.json` tenía el modelo escrito como
`moonshot/kimi-k3` en lugar de `moonshotai/kimi-k3`. OpenCode no
reconocía el nombre del proveedor y caía a un modelo de fallback más
caro en cada llamada al modelo. La evidencia está en los logs de
OpenCode, que mostraban el error literal `Model not found:
moonshot/kimi-k3. Did you mean: moonshotai, moonshotai-cn?`.

**Causas contribuyentes.**

1. La carpeta `.opencode/` del proyecto contenía un `opencode.json` que
   declaraba dos plugins fantasma (`opencode-supermemory` roto y
   `opencode-auto-resume`) que se cargaban en cada arranque, ensuciando
   el log y añadiendo overhead.
2. El plugin `@jimmyyen/opencode-context-cache`, que estabiliza la
   cache key de Moonshot, no estaba instalado. Sin él, la caché de
   prompt no se activaba y cada llamada pagaba la tarifa completa de
   input.
3. La actualización de OpenCode 1.18.32 a 1.18.35 (06/10/2026)
   probablemente introdujo el bug conocido de la opción `setCacheKey`
   en V2 (documentado en el PR #51956 de OpenCode).

**Evidencia empírica (Billing Details de la plataforma Moonshot AI).**

- 2026-10-03: $3.07 (configuración inicial + migración NVIDIA NIM →
  Moonshot directo)
- 2026-10-04: $4.05 (Fase 3.0 + 3.1.a)
- 2026-10-05: $5.14 (endurecimiento Fase 3.1.c, 7 commits)
- 2026-10-06: $13.75 (49% del gasto histórico total; incluye la
  actualización de OpenCode)
- 2026-10-07: $2.16
- Total histórico: $28.12 en Model Inference

Comparación antes/después de la corrección: el 10/10/2026, con la
configuración correcta (`moonshotai` + plugin de caché + plugins
fantasma eliminados), el coste fue $0.68 por 5 tareas más varios
arranques; con la configuración mala (días 05-06/10), el coste era de
~$1.50-2.00 por tarea similar.

**Verificación de gasto fantasma.** Se monitorizó el saldo durante 34
minutos sin actividad (13:15 a 13:49 del 10/10/2026). El saldo
permaneció idéntico ($30.76662) y el Today's Consumption también
($0.68236). No hay gasto fantasma por pings, sesiones latentes ni
procesos huérfanos. Los cargos que aparecían "retrasados" eran
liquidación diferida estándar de Moonshot (10 minutos de retraso del
panel).

**Solución aplicada.**

1. `opencode.json`: cambiado `moonshot/kimi-k3` a `moonshotai/kimi-k3`
   en los campos `model` y `small_model`.
2. Eliminada la carpeta `.opencode/` del proyecto (contenía los plugins
   fantasma).
3. Añadido el plugin `@jimmyyen/opencode-context-cache` al array
   `plugin` del `opencode.json` de la raíz.
4. Eliminada la opción `provider.moonshot.options.setCacheKey` (no
   funcionaba en V2).

**Reglas operativas derivadas.**

- Antes de arrancar cualquier cliente CLI (OpenCode, Kimi Code, etc.),
  verificar que el nombre del modelo en la configuración coincide con
  el nombre exacto que espera el cliente. Un typo produce fallback
  silencioso a modelos más caros.
- Evitar arrancar el cliente múltiples veces durante una sesión de
  trabajo. Cada arranque carga el repo-map completo del proyecto
  (~50-100K tokens) y genera el título de sesión automáticamente, con
  coste no despreciable. Preferir mantener una sesión abierta durante
  toda la sesión de trabajo.
- Documentar el coste por tarea y comparar con la expectativa. Si una
  tarea pequeña cuesta >$0.10, hay algo mal (modelo, caché, o
  configuración).

**Pendiente (no bloqueante).** Investigar cómo configurar el TTL de la
caché a 1 hora en OpenCode (actualmente el TTL efectivo es de 5 minutos
por defecto, lo que penaliza las pausas largas entre tareas). Es una
limitación conocida pero no bloqueante.

## Recorded architectural decisions

- **GUI**: PySide6 (not Streamlit). Reason: banking data confidentiality
  policy; data must not leave the analyst's desktop.
- **MCP**: added as an adapter in Phase 3; it does not replace the GUI.
- **White box**: sklearn/statsmodels/xgboost/lightgbm/catboost are forbidden.
- **Gini**: convention 2·AUC − 1 (credit scoring).
- **License**: Apache 2.0.
- **AI provider (dev-time only)**: Moonshot AI directo (Kimi K3) desde
  el 03/10/2026. No afecta al producto ni al runtime; es exclusivamente
  la herramienta de asistencia durante el desarrollo. Ver `AGENTS.md`.
- **Phase closure documentation: never deferred** (registrada el
  09/10/2026):
  - **Regla**: cuando una sub-fase cierra (commit pusheado, suite
    verde), la actualización de `docs/audit_log.md`, `docs/roadmap.md`
    y `docs/estado_proyecto.md` se hace EN EL MISMO BLOQUE de trabajo,
    no en una "sesión documental" aparte.
  - **Motivo**: aplazar la documentación desincroniza los documentos de
    contexto (`docs/contexto_para_nueva_sesion.md`,
    `docs/prompt_para_asistente.md`) respecto al estado real. Esto ya
    ocurrió en las sub-fases 3.1.d y 3.1.e: los commits `ef486d6` y
    `e44de70` se pushearon el 09/10, pero los documentos de contexto
    seguían hablando de "3.1.d/e pendientes" y de suite 206/221 cuando
    la suite real era 238. El coste se materializó al abrir un chat
    nuevo: hubo que reconstruir el estado cruzando git log + audit_log
    + salidas de PowerShell, consumiendo tiempo de trabajo técnico.
  - **Excepciones documentadas (solo dos)**: (a) indisponibilidad del
    servidor del proveedor de IA (504/timeout/quota); en ese caso, la
    entrada de audit_log y el sync de documentos se hace en cuanto el
    servicio vuelva, con nota explícita de la excepción; (b) cambios
    triviales de una línea que se commitean con el bloque mayor y se
    documentan en la misma entrada consolidada.
  - **Verificación obligatoria**: al cerrar cada sub-fase, además de
    pytest, `git status` y `git diff --stat`, se ejecuta un checklist de
    sincronización: `roadmap.md` refleja el estado,
    `estado_proyecto.md` refleja la suite real,
    `contexto_para_nueva_sesion.md` refleja el próximo paso,
    `prompt_para_asistente.md` refleja la herramienta activa. Si alguno
    no refleja el estado real, la sub-fase NO se considera cerrada.
  - **Contexto histórico**: la migración a OpenCode + Kimi K3 con key
    propia (sin la capa intermedia de NVIDIA NIM) elimina la causa
    técnica que históricamente forzaba aplazamientos (los 504
    recurrentes de NIM). A partir de ahora no hay excusa técnica para
    aplazar la documentación de cierre.
  - **Referencias cruzadas**: `docs/audit_log.md` entradas del
    09/10/2026 (migración OpenCode, hallazgo de caché), `.treegovrules`
    (política "no dejar cabos sueltos").

## Releases

- **v1.0.0a1** (03/10/2026) — Primera publicación real en PyPI.
  Incluye `backend_v3` (capa analítica) y `frontend_v3` (GUI PySide6).
  URL: https://pypi.org/project/treegov/1.0.0a1/
  - Publicada con `twine` 7.0.0 + token con scope de proyecto.
  - Verificada con instalación limpia desde PyPI en venv aislado.
  - Suite de tests: 199/199 PASSED.
- **v1.0.0a0** (fecha previa) — Placeholder reservado en PyPI. Solo
  metadatos, sin código funcional.

## Documentation map

The project's documentation is layered by purpose:

| Document | Purpose | Audience |
|---|---|---|
| `docs/methodology.md` | Mathematical formulas with citations | Auditor / modeller |
| `docs/design_decisions.md` | Implementation decisions (context, alternatives, rationale) | Auditor / maintainer |
| `docs/api.md` | Public API surface | Integrator |
| `docs/roadmap.md` | Phase plan and current status | Everyone |
| `docs/audit_log.md` | Chronological log of changes | Auditor |
| `docs/estado_proyecto.md` | Executive dossier of the project | New collaborator |
| `docs/contexto_para_nueva_sesion.md` | Bootstrap for new sessions | AI assistant / collaborator |
| `.treegovrules` | Governance rules | AI agent |
| `CONVENTIONS.md` | Operational conventions for Aider | AI agent |

**Rule.** A change that alters the numerical result, the API contract,
or the architectural boundaries must update `design_decisions.md` in
the same commit as the code. `methodology.md` gains a subsection only
when a mathematical formula or convention changes.

## Pending decisions

- **Distribution**: packaging method (PyInstaller / Inno Setup /
  MSI installer), digital signature, and distribution channel. To be
  decided before v1.0.
- **Commercial license format** (if ever considered): the current Apache
  2.0 is open source; a parallel commercial version would require
  legal analysis.