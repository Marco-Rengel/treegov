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
  Governance Mode (Regulatory/Research) added: Regulatory is the default;
  Research disables Jeffreys + PD Floor for non-banking domains (health,
  social sciences). Backend gained Session.describe_dataset() /
  fix_spec(predictors=...) / train(engine by name) /
  reset_to_data_loaded().
  - Test suite: 148/148.
- ✅ **Phase 2.2** (interactive tree viewer): QGraphicsView render with
  deterministic Reingold-Tilford layout, idempotent zoom (Ctrl + +/-),
  exclusive node selection, live retranslation, theme recolor.
  - Test suite: 158/158.
- ✅ **Phase 3.2** (sample weighting): weights transversal al backend
  (statistics, motores, tree_builder, session, validation, reporting,
  stability, wizard). 346/346 PASSED.

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
| 2.4.b Backend de reportes | ✅ Completada | `GainsTable` + `ClassificationMatrix` en `backend_v3/reporting.py`; 5 tests con valores verificados a mano |
| 2.4.c.1 Backend de Session | ✅ Completada | `get_gains_table` + `get_classification_matrix` en `Session`; 5 tests |
| 2.4.c.2.a Panel funcional | ✅ Completada | `reports_panel.py` + 65 claves i18n; sin Export HTML ni cableado |
| 2.4.c.2.b Cableado MainWindow | ✅ Completada | 4 señales conectadas + refresh tras entrenar/evaluar/cargar OOT |
| 2.4.c.2.c.1 Export HTML | ✅ Completada | QDialog + QTextBrowser + save-as |
| 2.4.c.2.c.2 Limpieza i18n | ✅ Completada | 14 claves huérfanas eliminadas |
| 2.4.c.2.c.3 Tests del panel | ✅ Completada | 7 tests unitarios en `tests/test_reports_panel.py` |
| 2.4.d Tests E2E + cierre | ✅ Completada | 4 tests E2E en `test_e2e_reports.py`; screenshot diferido a 2.4.e |

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
  ciencias sociales (referente: herramientas estadísticas clásicas de árboles de decisión, hoy descontinuadas).
- **Fase 3.x — Ponderación por muestra.** Para replicar flujo de buró
  (Equifax, Experian) donde la muestra está sesgada y se reajusta por
  pesos. No aplica a TreeGov hoy (*datasets* completos).
- **Fase 3.x — Categorías adicionales.** `Indet`, `Insufficient`,
  `No Perf` como metadatos de población (no entran al modelo). Relevante
  cuando se integre con sistemas de buró.

### ✅ Phase 3.1 — Multiclase (target + TreeNode + TreeBuilder + wizard + MetricsPanel)
**Priority: HIGH** · **Cerrada el 09/10/2026**

**Motivación.** Extiende la *pipeline* de construcción de árboles a targets
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

### ✅ Phase 3.3 — Population categories (Indet / Insufficient / No Perf)

**Desglose de la Fase 3.3:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.3.a | SessionState + Session: campos, caches, fix_spec, partition, load_oot, reset, describe_population_column | ✅ Completada |
| 3.3.b | TreeBuilder: population_col y population_ok_values en fingerprint | ✅ Completada |
| 3.3.c | reporting.build_oos_oot_report: rename n_excluded → n_excluded_routing + nuevos contadores de población | ✅ Completada |
| 3.3.d | Wizard: combo de población, regla espejo, tabla de valores OK, i18n | ✅ Completada |
| 3.3.e | Tests E2E del flujo de población + cierre documental | ✅ Completada |

**Cierre de la Fase 3.3.** Las 5 sub-fases (a-e) quedan cerradas el 11/10/2026. La categoría de población es un filtro opt-in declarado en `fix_spec`: filas cuyo valor de columna de población no está en la whitelist declarada se excluyen antes del split, antes del train y antes de la evaluación OOS/OOT; se reportan en `n_excluded_population` y `population_breakdown`. Invariante C1: sin `population_col`, comportamiento idéntico al pre-3.3. Suite: 377/377 PASSED.

### ✅ Phase 3.4 — Multiclass C&RT and QUEST

**Desglose de la Fase 3.4:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.4.a | C&RT multiclase: levantar el bloqueo en Session.train | ✅ Completada |
| 3.4.b | QUEST multiclase: Etapa 1 F de K grupos + tie-breaker BF K grupos; Etapa 2 QDA K=2 / barrido Gini K>2; retirar bloqueo; §3.8 en methodology | ✅ Completada |

**Cierre de la Fase 3.4.** Las dos sub-fases (a: C&RT; b: QUEST) quedan cerradas el 12/10/2026. Ningún motor bloquea ya targets con K > 2 en Session.train. Los bloqueos downstream (validation, reporting, stability) siguen activos hasta Fase 3.5. Invariante K=2: los motores producen modelos numéricamente idénticos al pre-3.4. *Fingerprint* sin cambios: la conducta multiclase se captura por `class_labels` / `n_classes` desde 3.1. Suite: 384/384 PASSED.

### ✅ Phase 3.5 — Multiclass and weighted reports

**Desglose de la Fase 3.5:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.5.a | validation.py multiclase + desbloqueo K>2 | ✅ Completada |
| 3.5.b | reporting.py multiclase + desbloqueo K>2 | ✅ Completada |
| 3.5.c | stability + Session: evaluate_oot multiclase | ✅ Completada |
| 3.5.d | auditoría de frontend + methodology + cierre documental | ✅ Completada |

**Cierre de la Fase 3.5.** Las cuatro sub-fases (a-d) cierran el *pipeline*
completo de validación, reporte y monitoreo a targets multiclase
(K ≥ 2) con composición ponderada. 3.5.a abrió compute_oos_metrics con
D15-D17. 3.5.b abrió build_gains_table y build_classification_matrix
con D18-D20 y cerró el diferido §13.7 para el path multiclase (D13).
3.5.c desbloqueó evaluate_oos, evaluate_oot y get_classification_matrix
a nivel Session (traducción de etiquetas al orden interno en Session,
Z2). 3.5.d auditó el frontend (cero cambios obligatorios; tres mejoras
cosméticas diferidas a H4), publicó las subsecciones §8.11-§8.14 de
methodology y cerró la documentación.

**Invariante no negociable**: para K=2 con weights None o uniformes,
todo el *pipeline* es idéntico bit a bit al pre-3.5, salvo por los campos
aditivos de los DTOs que quedan vacíos (excepto accuracy, poblado en
ambos modos). Suite: 411/411 PASSED.

**Deuda diferida**:
- Tres mejoras cosméticas del ReportsPanel (fila accuracy, fila "n por
  clase", título "clase de interés vs resto" en K>2) se agrupan en el
  rediseño H4.
- Las subsecciones §8.11-§8.14 de methodology.md no cubren todavía el
  ROC one-vs-rest por clase (D8/D17); el DTO expone las K curvas pero
  el documento matemático no las formaliza. Se difiere a la Fase 3.6
  si el caso de uso lo exige.
- ✅ Cerrado el 16/10/2026: los tres cosméticos del ReportsPanel (fila accuracy, fila "n por clase", título multiclase K>2) fueron implementados, testeados (5 tests nuevos, suite 411 → 416) y documentados en docs/audit_log.md entrada del 16/10/2026. Ya no se difieren a H4.

**Traducción de etiquetas al orden interno (Z2).** La traducción
{viejo → índice interno} vive dentro de Session, en el helper privado
_translate_y_to_internal. No toca la firma pública de
compute_oos_metrics ni de stability.py. En K=2 el helper no se
invoca: el camino binario queda intacto bit a bit.

**Asimetría diferida registrada (D13 literal).** El path binario de
build_gains_table conserva _discrimination_metrics sin ponderar incluso
con pesos; el path multiclase llama a compute_oos_metrics que sí
pondera. La asimetría respeta el invariante no negociable y está
documentada en el diseño §1.2 y en audit_log (entrada 15/10/2026).

### ✅ Phase 3.6 — Public-dataset validation

**Desglose de la Fase 3.6:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.6.a | Diseño del plan de validación (6 datasets UCI, contrato CSV TreeGov-ready, script de descarga con SHA256, fixtures versionadas, informe de validación) | ✅ Completada |
| 3.6.b | Script de descarga (scripts/fetch_datasets.py) + fixtures versionadas (tests/fixtures/uci/) | ✅ Completada |
| 3.6.c | Tests de integración (tests/test_uci_integration.py) + script de validación (scripts/validate_uci.py) + informe de resultados (docs/validation_results_3.6.md) | ✅ Completada |
| 3.6.d | Cierre documental de la fase | ✅ Completada |
| 3.6.e | Modo no-bancario (terminología neutral + ejemplos + validación multi-dominio extensiva: marketing, ecología) | ⏳ |

**Cierre de 3.6.a (16/10/2026).** El diseño completo vive en `docs/3.6_design_public_datasets.md` (811 líneas). Nueve decisiones D1-D9: tres *datasets* (German Credit, Car Evaluation, Balance Scale) para cubrir tres ejes (binario/multiclase × categórico/ordinal/numérico × balanceado/desbalanceado); script de descarga con verificación SHA256; contrato de CSV "TreeGov-ready"; fixtures completas versionadas en lugar de subset+skip; matriz de costes de German Credit ignorada explícitamente; entregable triple (scripts + informe + tests); Balance Scale permanece ORDINAL; baseline propio + comentario cualitativo de literatura; códigos originales de UCI preservados. Sin cambios de código: `backend_v3/` no se toca.

**Ampliación de alcance (16/10/2026, tarde).** En la sesión del mismo día se decidió ampliar el conjunto de *datasets* de 3 *datasets* (todos bancarios o neutros) a 6 (cuatro dominios: banca, salud, biología, ciencias sociales). Motivo: el README declara seis dominios objetivo (banca, salud, ciencias sociales, marketing, biología, ecología) y 3.6 con 3 *datasets* cubría solo uno. Nuevas decisiones D10 (añadir Breast Cancer WDBC, Iris, Blood Transfusion) y D11 (diferir marketing y ecología a 3.6.e). Detalle en `docs/3.6_design_public_datasets.md` §2.4–§2.7 y `docs/audit_log.md` entrada del 16/10/2026.

**Cierre de la Fase 3.6.** Completada el 16/10/2026. Validación cruzada con 6 *datasets* en 4 dominios. Suite: 422/422 (416 previos + 6 tests de integración UCI).

## Upcoming phases

### ⏳ Phase 3 — Advanced analytics + documentation closure
**Priority: HIGH**

**Objetivo.** Cerrar la "zona gris" de decisiones implícitas acumuladas en
Fases 0-2, y extender la analítica del motor para cubrir los casos de uso
reales de crédito (muestras sesgadas, categorías Indet/No Perf, multiclase)
y no-crédito (biología, ciencias sociales).

**Sub-fases:**

| Sub-fase | Alcance | Prioridad |
|---|---|---|
| 3.0 | ✅ Documentación + parámetros canónicos vs TreeGov (design_decisions.md + 4 parámetros) | Completada |
| 3.1 | ✅ Multiclase en el árbol (target + TreeNode + TreeBuilder + wizard + MetricsPanel) | Completada |
| 3.2 | ✅ Ponderación por muestra (transversal al backend) | Completada |
| 3.3 | ✅ Categorías de población (Indet / Insufficient / No Perf) | Completada |
| 3.4 | CRT y QUEST multiclase | Completada |
| 3.5 | Reportes adaptados (multiclase + ponderación) | Completada |
| 3.6 | Validación con datasets públicos (6 datasets UCI: German Credit, Car Evaluation, Balance Scale, Breast Cancer WDBC, Iris, Blood Transfusion) | Completada |
| 3.6.e | Modo no-bancario (terminología + ejemplos + docs) | Media |
| 3.7 | Cierre Fase 3 + v1.0.0 estable | Alta |
| 3.7.a | ✅ Auditoría de seguridad y privacidad (retención de logs, advertencias GUI, modelo de amenazas) antes de la v1.0.0 | Completada |
| 3.7.b | ✅ Simetrizar el estadístico KS por pares en validation.py (promediar KS_ij y KS_ji) y actualizar methodology.md | Completada |
| 3.7.c | ✅ Exponer `min_child_weight` en la firma de `Session.train` y cablearlo en el asistente gráfico (actualmente es un parámetro interno de TreeBuilder) | Completada |
| 3.7.d | Ampliar tests/test_uci_integration.py para incluir aserciones de CHAID (Car Evaluation, Balance Scale) y QUEST (los 6 datasets) | Alta |

**Desglose de la Fase 3.2:**

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.2.a | statistics.py ponderado (f_oneway, brown_forsythe) | ✅ Completada |
| 3.2.b | CHAID con conteos ponderados (χ²/F + merging + Cochran) | ✅ Completada |
| 3.2.c | C&RT con Gini/varianza ponderada + surrogates | ✅ Completada |
| 3.2.d | QUEST con Stage 1 + QDA ponderados | ✅ Completada |
| 3.2.e | TreeBuilder (weights + min_child_weight + fingerprint) | ✅ Completada |
| 3.2.f | Session (fix_spec + partition + train + reset) | ✅ Completada |
| 3.2.g | validation y reporting ponderados | ✅ Completada |
| 3.2.h | stability ponderado + wizard + E2E + cierre | ✅ Completada |

**Cierre de la Fase 3.2.** Las 8 sub-fases (a-h) quedan cerradas el 10/10/2026. La ponderación por muestra es transversal al backend: motores, árbol, sesión, métricas, reportes, monitoreo y wizard. Invariante C1: sin pesos, comportamiento idéntico al pre-3.2. Tres parámetros nuevos en el *fingerprint*: weighted, weight_col, min_child_weight. Tres decisiones diferidas registradas en design_decisions.md §13.7 (KS/AUC/Gini del gains table sin ponderar), §13.8 (HL escala con la masa), §13.9 (nombre del parámetro weight_oot). Suite: 346/346 PASSED.

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
- El fixture _make_csv de los tests E2E (target aleatorio respecto a
  predictores) sigue pendiente de reemplazo por uno con señal real.
  Sin cambios en 3.5.a.

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

### ⏳ PyPI refresh: publish 1.0.0a2
**Priority: MEDIUM (deferred, target: after Phase 3.3 closes)**

The PyPI page for treegov 1.0.0a1 still shows the README frozen at the
03/10/2026 publication: 199/199 tests and the pre-reframing regulatory
notice. The repo README already reflects 346/346 and the opt-in
governance framing. To update PyPI, publish 1.0.0a2: bump version in
pyproject.toml and frontend_v3/__init__.py, rebuild, twine check, twine
upload, verify with a clean install in an isolated venv. Target: after
Phase 3.3 closes, before Phase 3.4 starts. Not a blocker for 3.3.a.

### ✅ OpenCode token consumption — learning from Fase 3.2 block (10/10/2026)
**Priority: LOW (resolved, no longer blocking).**

Refinamiento del 11/10/2026. El análisis del bloque de la Fase 3.2 (10/10/2026) se completa con las métricas del Caching Overview y el Product Bill de la consola de Moonshot, capturadas el 11/10/2026. Dos lecturas correctas que miden cosas distintas: (a) 93.8 por ciento de los tokens de input vienen de caché (métrica operativamente relevante: mide eficiencia del prefijo cacheado); (b) el peso del Context Caching sobre el coste total del bloque fue 53 por ciento (métrica de coste: mide cuánto del gasto se fue en la capa de caché). La primera es la que importa para decidir política operativa: el caché está prácticamente al techo, y reducir el tamaño del prefijo ya no aporta ahorro significativo. El desglose por producto del rango 04/10 a 10/10 (Beijing) muestra la estructura real del coste: completion (output) 55 por ciento del total, Cache Write 5m 24 por ciento, auto-caching (read) 19 por ciento, Cache Write 1h 1 por ciento, prompt (input fresco) 0.4 por ciento. Los tres levers reales, en orden de impacto: (1) respuestas cortas del modelo, porque el output cuesta cinco veces el input; (2) prompts quirúrgicos que eviten lecturas de archivos enteros, porque el input fresco, aunque barato, se acumula; (3) no romper el TTL de 5 minutos dentro de una sub-fase, porque cada expiración paga write premium. El tier de caché de 1 hora ya está operando sin plugin custom (0.48 USD facturados en el rango). Pendiente diferido: analizar los logs de OpenCode del 10/10 para desglose por tarea con la pestaña Export Records, y evaluar Kimi K2.6 o K2.7-code para tareas simples.

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

**Reglas operativas derivadas (versión refinada 10/10/2026, tarde).**

- Antes de arrancar cualquier cliente CLI, verificar que el nombre del modelo en la configuración coincide exactamente con el nombre que espera el cliente. Un typo produce fallback silencioso a modelos más caros.
- Dentro de cada sub-fase: mantener el cliente abierto, ráfaga sin cerrar entre prompts de código, tests y documentación.
- Al cerrar una sub-fase (commit pusheado): cerrar el cliente. El prefijo vuelve a ser pequeño al reabrir y no arrastra contexto de sub-fases anteriores.
- El cierre documental de una fase se trata como una unidad: los prompts de documentación de cierre van seguidos sin cerrar entre ellos.
- Prompts quirúrgicos: nombrar líneas exactas cuando se edita código. Evitar que el agente lea archivos enteros.
- Instrucciones de respuesta corta: el output del modelo cuesta cinco veces más que el input nuevo.
- Documentar el coste por sub-fase. Referencia de Fase 3.2: dos dólares veintinueve centavos por sub-fase. Si una sub-fase futura excede tres dólares, diagnosticar.
- **Nivel de razonamiento del agente (Fase 3.3).** Default `high`. `max` obligatorio para: (a) cambios de firma de funciones públicas, (b) sub-fases con múltiples archivos, (c) refactors estructurales, (d) depuración de bugs. `low` NUNCA es válido para trabajo técnico. Durante la Fase 3.3.d el nivel quedó en `low` tras una actualización de OpenCode, y produjo 15 fallos evitables (firmas desalineadas, cfgs de test sin actualizar). Verificado el 11/10/2026: `max` detecta estos errores antes de escribir el código.
- **Auditoría de consumidores antes de cambiar firmas públicas.** Cuando una función gana parámetros obligatorios, TODOS sus consumidores deben buscarse y adaptarse en el mismo bloque, no dejarlo para la sub-fase siguiente. Los 15 fallos de 3.3.d provienen de no haber auditado los helpers `_cfg()` de los tests E2E antes de tocar `_train_pipeline`.
- **Un prompt = un archivo, verificación al final del bloque.** La regla de ráfaga se refuerza: una sub-fase completa se manda en ráfaga (todos los prompts seguidos) y se verifica UNA sola vez al final. Enviar prompts de uno en uno con verificación intermedia rompe la caché y multiplica el coste.
- Evaluar modelos más baratos para tareas de bajo razonamiento (documentación, formateo).

**Pendientes abiertos.** Investigar el hueco de dos dólares noventa y siete centavos del bloque 3.2 con la pestaña Export Records del panel de Moonshot. Analizar los logs de OpenCode del 10/10 para desglose por tarea. Evaluar el TTL de una hora de caché (requiere plugin custom). Evaluar Kimi K2.6 o K2.7-code para tareas simples.

### UX findings from first GUI session (13/10/2026) — Deferred
Priority: Low (deferred, not blocking).

La primera sesión de visualización end-to-end de la GUI (13/10/2026) identificó 8 hallazgos de usabilidad y estética. Ninguno es bug funcional. Se documentan aquí como deuda diferida. La fuente de verdad es la entrada del 13/10/2026 en `docs/audit_log.md`.

- H1 — Radio buttons del asistente invisibles (motor en Paso 1, clase de interés en Paso 2). Prioridad Alta.
- H2 — Target por defecto del asistente es la primera columna del CSV. Prioridad Alta.
- H3 — Botones de mover predictores se ven como texto plano. Prioridad Media.
- H4 — Paleta y layout del visor del árbol y del panel de reportes frente al prototipo previo. Prioridad Media.
- H5 — Opción Cross-validation del Paso 3 deshabilitada sin explicación al usuario. Prioridad Baja.
- H6 — Datos sensibles en logs DEBUG y reports HTML exportados. Seguridad transversal y política de datos para v1.0.0. Prioridad Alta.
- H7 — Matriz de clasificación con umbral 0.5 degenerada en targets con baja tasa de eventos. Prioridad Media.
- H8 — Tema oscuro demasiado oscuro, sin jerarquía visual entre fondo y paneles. Prioridad Media.

**Motivo del aplazamiento.** Ninguna de las fases pendientes (3.5, 3.6, 3.7) requiere cerrar estos hallazgos para avanzar. Se planifican en una sub-fase específica de rediseño UX posterior a la Fase 3.5, o como bloque pre-release dentro de la Fase 3.7 en el caso de H6 (seguridad y datos sensibles).

### ✅ Pendiente Aider/build/twine en el .venv del proyecto
**Priority: LOW (resolved 16/10/2026).**

Detectado el 12/10/2026 que aider-chat 0.86.2 (más build 1.6.1 y twine 7.0.0) estaban instalados dentro del .venv del proyecto, violando la regla del 27/09/2026 ("CLI tools via pipx, nunca en el .venv del proyecto"). El pendiente quedó anotado en la conversación pero NO se registró en este roadmap.

Resuelto el 16/10/2026: los tres paquetes desinstalados del .venv. pip check limpio. Suite 416/416. aider --version sigue respondiendo 0.86.2 desde pipx. Los tres binarios de pipx (aider.exe, pyproject-build.exe, twine.exe) siguen operativos en C:\Users\maren\.local\bin.

Hallazgo importante: Aider YA estaba correctamente instalado en pipx desde el 28/09/2026. La causa raíz del conflicto fue la instalación de build/twine dentro del .venv el 12/10/2026, que subió packaging 26.0→26.3 y rich 14.3.2→15.0.0, rompiendo los pins de Aider. Aider era víctima, no causa.

Deuda residual: ~100 paquetes huérfanos en .venv (dependencias únicas de Aider/build/twine). No afectan runtime. Reconstrucción limpia del .venv diferida a sesión propia, con pip freeze previo.

Detalle completo en docs/audit_log.md entrada del 16/10/2026.

## Recorded architectural decisions

- **GUI**: PySide6 (not Streamlit). Reason: banking data confidentiality
  policy; data must not leave the analyst's desktop.
- **MCP**: added as an adapter in Phase 5; it does not replace the GUI.
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
- **Toda deuda detectada se registra en el roadmap (16/10/2026).** Cuando se detecta una deuda técnica o un pendiente, se registra en este documento (sección Deferred o Pending decisions) EN LA MISMA SESIÓN en que se detecta. No basta con mencionarlo en audit_log.md o en la conversación. Motivo: el pendiente Aider/build/twine del 12/10/2026 estuvo abierto 4 días sin trazabilidad en el roadmap; al retomarlo el 16/10 hubo que reconstruir el contexto desde cero. El roadmap es la fuente de verdad de deuda técnica del proyecto; el audit_log es la bitácora cronológica.
- **Cierre de pendientes cosméticos (18/10/2026).** Los tres pendientes cosméticos detectados en el móvil el 17/10/2026 quedan cerrados en el commit 7334f65 (bloque de documentación pura, suite 422/422 intacta): (a) mención de CHAID Exhaustive restaurada en README.md y README.es.md; (b) tabla "¿Por qué TreeGov?" solo en español en README.es.md; (c) comillas tipográficas y título corregido en README.md y docs/philosophy.md. Ver docs/audit_log.md entrada del 18/10/2026.

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
  2.0 is *open source*; a parallel commercial version would require
  legal analysis.
