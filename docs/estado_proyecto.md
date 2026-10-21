# TreeGov — Estado del Proyecto y Contexto para Auditoría

**Fecha de última actualización:** 18/10/2026 (Fase 3.7 cerrada, release 1.0.0rc1)
**Autor:** Marco Rengel
**Propósito:** Resumen ejecutivo del estado técnico, decisiones arquitectónicas
y trazabilidad del proyecto, apto para:
1. Reconstruir contexto en una nueva sesión de trabajo asistido por IA.
2. Servir como dossier introductorio para un auditor/validador MRM.

---

## 1. Identificación del proyecto

| Campo | Valor |
|---|---|
| Nombre | TreeGov — Risk Segmentation Workbench |
| Versión | 1.0.0rc2 (release candidate) |
| Licencia | Apache 2.0 |
| GitHub | github.com/Marco-Rengel/treegov (privado) |
| PyPI | https://pypi.org/project/treegov/1.0.0rc2/ |
| Autor | Marco Rengel (marcrengel@gmail.com) |
| Motor gráfico | PySide6 |
| Motor analítico | Python (NumPy, pandas, scipy.stats) |
| Modelo de IA en desarrollo | OpenCode 1.19.0 (cliente activo desde 09/10/2026) + Kimi K3 vía Moonshot AI directo con key propia de Moonshot (NO vía NVIDIA NIM). Aider 0.86.2 como respaldo documentado (pipx, Python 3.11.9). Migración de NVIDIA NIM a Moonshot el 03/10/2026 (factura 2846-0745, NOVASCENT/Singapur) por inestabilidad de NIM (504 recurrentes) |

---

## 2. Resumen ejecutivo

TreeGov es una herramienta de segmentación analítica para riesgo de crédito
con gobernanza MRM/IFRS 9 nativa. Implementa los algoritmos clásicos de
árboles de decisión (CHAID, C&RT, QUEST) con matemática de caja blanca
auditable, sin dependencia de librerías de caja negra (sklearn/statsmodels).

**Diferenciador principal:** la gobernanza no es una capa añadida al final,
sino un principio integrado en cada componente. Esto se traduce en:
- Configuración inmutable (SplitConfig frozen) como evidencia auditable.
- Logging DEBUG transaccional por corrida.
- Fórmulas estadísticas explícitas en el código con cita bibliográfica.
- Bloqueo de librerías de caja negra a nivel de import guard.

---

## 3. Estado técnico por fase

### Fase 0 — Núcleo algorítmico ✅ Completada

Módulos:
- `backend_v3/import_guard.py` — bloqueo de sklearn/statsmodels/xgboost/lightgbm/catboost
- `backend_v3/log_config.py` — logger `treegov` con doble handler (archivo + consola)
- `backend_v3/types.py` — SplitConfig frozen + enums (TargetType, PredictorType, CutKind)
- `backend_v3/statistics.py` — χ² Pearson, F ANOVA, Brown-Forsythe, Stirling, multiplicadores de Kass
- `backend_v3/chaid_engine.py` — CHAID clásico + Exhaustive CHAID (multiclase)
- `backend_v3/crt_engine.py` — C&RT binario + surrogate splits
- `backend_v3/quest_engine.py` — QUEST binario con QDA univariante
- `backend_v3/imputation.py` — TrainOnlyImputer (anti-leakage)
- `treegov.py` — orquestador headless

Rendimiento verificado: N=1M filas, peor caso 0.29 s/evaluación (objetivo <1.5s).

### Fase 1 — Flujo transaccional ✅ Completada

Módulos:
- `backend_v3/splitting.py` — Hamilton-Hare estratificado exacto
- `backend_v3/profiling.py` — inferencia de tipos de predictores
- `backend_v3/tree_builder.py` — TreeBuilder (BFS determinista) + TreeModel + TreeNode
- `backend_v3/session_state.py` — FlowState + SessionState + Session (máquina de estados)

### Fase 1.2 — Evaluación OOS + poda ✅ Completada

Módulos:
- `backend_v3/validation.py` — métricas OOS (Gini, KS, HL, Brier, ROC, PR-AUC)
- `backend_v3/pruning.py` — poda coste-complejidad de Breiman

### Fase 1.3 — OOT + monitoreo de estabilidad ✅ Completada

Módulos:
- `backend_v3/stability.py` — PSI (hojas), CSI (covariables), Gini Drop
- Extensiones de `session_state.py`: load_oot, evaluate_oot, estados OOT_LOADED/OOT_EVALUATED

### Fase 2.0 — Esqueleto GUI ✅ Completada

Módulos:
- `frontend_v3/app.py` — QApplication + excepthook a `treegov.gui` + auto-quit CI
- `frontend_v3/main_window.py` — QMainWindow (menús, splitter 3 paneles, status bar)
- `frontend_v3/theme.py` — temas light/dark vía QSS + string.Template
- `frontend_v3/i18n.py` — diccionario bilingüe EN/ES + LanguageBus
- `frontend_v3/resources/styles.qss` — plantilla de estilos
- `treegov_gui.py` — entry point

### Fase 2.1 — Wizard transaccional + Governance Mode ✅ Completada

Módulos:
- `frontend_v3/wizard.py` — ModelWizard (4 pasos) con retraducción en caliente
- `backend_v3/types.py` — GovernanceMode (BANKING / RESEARCH)
- `backend_v3/tree_builder.py` — apply_jeffreys, pd_floor anulable, fingerprint con governance_mode
- `backend_v3/session_state.py` — describe_dataset, reset_to_data_loaded,
  fix_spec(predictors=...), train(engine por nombre, apply_jeffreys, pd_floor)
- `backend_v3/profiling.py` — helper interno _infer_column (reuso sin duplicar)

### Fase 2.2 — Visor interactivo de árbol ✅ Completada

Módulos:
- `frontend_v3/tree_view.py` — NodeItem, TreeScene, TreeView, TreePanel
  (zoom idempotente, layout determinista Reingold-Tilford, retraducción en
  caliente, recoloreo por tema).
- Extensión de `main_window.py`: pestaña Tree con HUD de propiedades del nodo.

### Fase 2.3 — Panel de métricas OOS/OOT ✅ Completada

Sub-fases completas:
- 2.3.a Diseño estructural ✅
- 2.3.b 23 claves i18n ✅
- 2.3.c Esqueleto del panel + 3 tests ✅
- 2.3.d Backend de reporting (`reporting.py` + `Session.get_oos_oot_report()`) + 6 tests ✅
- 2.3.e.1 Normalización de semáforos (alfabeto backend en inglés) ✅
- 2.3.e.2 Claves i18n por estado ✅
- 2.3.e.3 Tokens QSS semánticos ✅
- 2.3.e.4 MetricsPanel funcional ✅
- 2.3.e.5 Cableado MainWindow ↔ MetricsPanel ✅
- 2.3.f Tests E2E + cierre ✅

El panel OOS/OOT está operativo end-to-end: carga datos, entrena,
evalúa OOS, carga OOT, evalúa, y renderiza badges con colores semánticos
del tema activo.

### Fase 2.4 — Reportes + integración ✅ Completada

Sub-pasos:
- 2.4.a Diseño estructural ✅ — Pestaña Reports +
  `reports_panel.py` (placeholder) + 2 claves i18n + tests ajustados.
- 2.4.b Backend de reportes (`GainsTable` + `ClassificationMatrix`) ✅
- 2.4.c.1 Backend de Session (`get_gains_table` + `get_classification_matrix`) ✅
- 2.4.c.2.a Panel funcional (`reports_panel.py` + i18n) ✅
- 2.4.c.2.b Cableado MainWindow ✅
- 2.4.c.2.c.1 Export HTML ✅
- 2.4.c.2.c.2 Limpieza i18n ✅
- 2.4.c.2.c.3 Tests del panel ✅
- **2.4.c.2 completa** ✅
- 2.4.d Tests E2E + cierre ✅
- **Fase 2.4 completa** ✅

Diseño completo en `docs/roadmap.md` (sección Fase 2.4).

### Fase 3.0 — Cierre de zona gris documental ✅ Completada

Módulos y documentos:
- `docs/design_decisions.md` (nuevo) — 44 subsecciones documentando las
  decisiones de implementación de Fases 0-2 que no estaban en
  `methodology.md` ni en `audit_log.md`.
- `docs/methodology.md` — 16 subsecciones nuevas (§1.7-§8.10) con las
  fórmulas y convenciones numéricas que faltaban.
- 4 parámetros configurables expuestos (canónico vs TreeGov):
  - `QuestEngine.bonferroni_family` (default 2).
  - `QuestEngine.nominal_high_card` (default "rate").
  - `QuestEngine.qda_root_restriction` (default True).
  - `StabilityMonitor.renormalize` / `psi_index.renormalize` (default False).
- `docs/roadmap.md` — redefinición de las fases 3-7 (la Fase 3 original
  mezclaba tres familias de trabajo).

### Fase 3.1 — Multiclase ✅ Completada

**Diseño estructural completado** (04/10/2026):
- `docs/3.1_design_multiclass.md` (nuevo, ~40 KB, 13 secciones).

**Alcance de 3.1**: abrir `TreeNode`, `TreeModel`, `TreeBuilder` y
`Session.fix_spec` a targets con K ≥ 2 clases. Solo CHAID (C&RT y QUEST
bloquean K > 2 hasta Fase 3.4). Métricas y reportes siguen siendo
binarios hasta Fase 3.5.

**Decisiones clave**:
- `pd_final`, `pd_jeffreys`, `n_events` pasan a `tuple[...]`.
- Nuevo campo `TreeNode.class_labels`.
- `target_class` y `class_labels` son **obligatorios** en `Session.fix_spec`.
- Jeffreys multivariante: `(k_c + 0.5) / (n + K * 0.5)`.
- Reordenamiento canónico interno: la clase de interés siempre en índice 0.
- Wizard con validación pre-entrenamiento (3 checks) y alertas
  post-entrenamiento (badge de Gini negativo + botón de reversión).

**Sub-fases** (6, todas cerradas):
- 3.1.a — `TreeNode`/`TreeModel` tuple fields + `TreeBuilder.target_class` ✅
- 3.1.b — Jeffreys multivariante + floor renormalizado + reordenamiento ✅ (integrado en 3.1.a)
- 3.1.c — `Session.fix_spec` + `SessionState` + bloqueo C&RT/QUEST ✅
- 3.1.d — `predict_pd` 2D + bloqueos en validation/reporting/stability ✅
- 3.1.e — Wizard multiclase: tabla de clases + counts + warning minoritaria ✅
- 3.1.f — MetricsPanel: badge Gini negativo + botón de reversión ✅

CHAID y CHAID_EXHAUSTIVE son los únicos motores que admiten K>2 en 3.1;
C&RT y QUEST se abren en Fase 3.4. Las métricas y reportes siguen
binarios hasta Fase 3.5. Invariante no negociable: para K=2 con
target_class=1 y labels estándar, el modelo es numéricamente idéntico
al pre-3.1.

### Fase 3.2 — Ponderación por muestra ✅ Completada

**Alcance**: ponderación por muestra transversal al backend (motores,
árbol, sesión, métricas, reportes, monitoreo y wizard). Invariante C1:
sin pesos, comportamiento idéntico al pre-3.2.

**Sub-fases** (8, todas cerradas el 10/10/2026):
- 3.2.a — statistics.py ponderado (f_oneway, brown_forsythe) ✅
- 3.2.b — CHAID con conteos ponderados (χ²/F + merging + Cochran) ✅
- 3.2.c — C&RT con Gini/varianza ponderada + surrogates ✅
- 3.2.d — QUEST con Stage 1 + QDA ponderados ✅
- 3.2.e — TreeBuilder (weights + min_child_weight + fingerprint) ✅
- 3.2.f — Session (fix_spec + partition + train + reset) ✅
- 3.2.g — validation y reporting ponderados ✅
- 3.2.h — stability ponderado + wizard + E2E + cierre ✅

Tres parámetros nuevos en el *fingerprint*: `weighted`, `weight_col`,
`min_child_weight`. Tres decisiones diferidas en `design_decisions.md`
(§13.7, §13.8, §13.9). Suite: 346/346.

### Fase 3.3 — Categorías de población ✅ Completada

**Alcance**: filtro *opt-in* de población, declarado en fix_spec como
columna auxiliar del CSV. Filas cuyo valor no está en la whitelist de
valores OK se excluyen antes del *split*, antes del train y antes de la
evaluación OOS/OOT, y se reportan en `n_excluded_population` +
`population_breakdown` (desglose por motivo). Invariante C1: sin
`population_col`, comportamiento idéntico al pre-3.3.

**Sub-fases** (5, todas cerradas el 11/10/2026):

- 3.3.a — `SessionState` y `Session`: campos, caches, `fix_spec`, `partition`, `load_oot`, `reset_to_data_loaded`, `describe_population_column` ✅
- 3.3.b — `TreeBuilder`: `population_col` y `population_ok_values` en fingerprint ✅
- 3.3.c — `reporting.build_oos_oot_report`: rename `n_excluded` → `n_excluded_routing` + nuevos contadores ✅
- 3.3.d — Wizard: combo de población, regla espejo, tabla de valores OK, i18n ✅
- 3.3.e — Tests E2E del flujo de población + cierre documental ✅

Dos parámetros nuevos en el *fingerprint*: `population_col`,
`population_ok_values`. Suite: 384/384.

### Fase 3.5 — Reportes multiclase y ponderados ✅ Completada

**Alcance**: abrir los tres puntos de bloqueo remanentes de la Fase
3.1.d (validation, reporting y Session.evaluate_oot) a targets con
K > 2 y componer con el modo ponderado de la Fase 3.2. Cuatro
sub-fases (a-d). Invariante no negociable: para K=2 con weights None
o uniformes, el resultado es idéntico bit a bit al pre-3.5.

**Sub-fases**:

- 3.5.a — validation.py multiclase + desbloqueo K>2. ✅ Completada.
- 3.5.b — reporting.py multiclase + desbloqueo K>2. ✅ Completada.
- 3.5.c — stability + Session: evaluate_oot multiclase. ✅ Completada.
- 3.5.d — auditoría de frontend + methodology + cierre documental. ✅ Completada.

**Cierre de la Fase 3.5 (a-d)**. El *pipeline* completo de validación,
reporte y monitoreo admite targets multiclase (K ≥ 2) combinados con
ponderación por muestra. 3.5.a abrió compute_oos_metrics (D15-D17).
3.5.b abrió las dos funciones de reporte y cerró el diferido §13.7
para el path multiclase (D13, D18-D20). 3.5.c desbloqueó
evaluate_oos/evaluate_oot/get_classification_matrix a nivel Session
(traducción de etiquetas al orden interno en Session, Z2). 3.5.d
auditó el frontend (cero cambios obligatorios; tres cosméticos
diferidos a H4), publicó §8.11-§8.14 en methodology y cerró la
documentación. Invariante K=2 bit a bit preservado. Suite 416/416
PASSED.

### Fase 3.8 — Corrección de atribución regulatoria (BCBS CRE 32.4) ✅ Completada

**Motivación.** Una auditoría externa detectó que el proyecto atribuía
el piso de PD (PD Floor) a "BCBS CRE 20.39" con un valor de 0.03%.
Ambas dimensiones eran incorrectas: CRE 20.39 regula *covered bonds*,
no el piso de PD; y 0.03% era el piso de Basel II, no el vigente. La
reforma de Basel III (2017) estableció el piso en 0.05% para
corporativos, bancos y retail en el apartado CRE 32.4 (con excepción
soberana de 0.03%).

**Cambios aplicados.**
- Default de `pd_floor` en `Session.train` y `TreeBuilder` actualizado
  de `0.0003` a `0.0005`.
- Atribución normativa corregida a BCBS CRE 32.4 en todo el código y
  documentación.
- PSI/CSI (`stability.py`) reatribuido de "Basel/EBA" a Siddiqi (2006)
  como convención de la industria.
- Wizard e i18n alineados con el nuevo default y cita.
- 14 fingerprints de UCI recapturados; métricas numéricas intactas
  (el floor no se activa bajo el `min_child_size` actual).
- 3 tests nuevos para anclar el comportamiento del nuevo default.

**Nota sobre la excepción soberana.** La excepción (0.03%) no está
modelada por defecto; analistas con exposición soberana deben pasar
`pd_floor=0.0003` explícitamente. El disclaimer está documentado en
el código y en `docs/methodology.md` §6.3.

**Suite:** 434/434 PASSED.

### Cierre intermedio 16/10/2026

Cerrados los tres cosméticos del ReportsPanel diferidos a H4 en el cierre 3.5.d (fila accuracy, fila "n por clase", título multiclase K>2). Añadidos 5 tests. Suite 416/416. Resuelto también el pendiente de herramientas CLI duplicadas en el .venv del proyecto (aider-chat, build, twine; ver docs/audit_log.md entrada del 16/10/2026). Sin cambios de código analítico.

**Adicional 16/10/2026, tarde.** Cerrada la sub-fase 3.6.a (diseño del plan de validación con datasets públicos). El documento `docs/3.6_design_public_datasets.md` (811 líneas) define nueve decisiones D1-D9 aprobadas por el autor: tres *datasets* de UCI (German Credit binario, Car Evaluation multiclase categórico K=4, Balance Scale multiclase ordinal K=3); script de descarga con verificación SHA256; contrato de CSV TreeGov-ready; fixtures completas versionadas en `tests/fixtures/uci/` (~150 KB) en lugar de subset + skip; matriz de costes de German Credit ignorada; entregable triple (scripts + informe + tests); baseline propio cuantitativo + comentario cualitativo de literatura. Sin cambios de código: `backend_v3/` no se toca, suite 416/416 intacta.

### Fases pendientes

- **Fase 2.1.b** — Extras de endurecimiento (validación cruzada, guardrail runtime de imports backend)
- **Fase 3.3** — Categorías de población ✅ Completada
- **Fase 3.4** — CRT y QUEST multiclase. ✅ Completada (3.4.a C&RT + 3.4.b QUEST).
- **Fase 3.5** — Reportes adaptados (multiclase + ponderación). ✅ Completada (4 sub-fases a-d).
- **Fase 3.6.a** — Diseño del plan de validación con *datasets* públicos. ✅ Completada (`docs/3.6_design_public_datasets.md`, commit `1df08b0`).
- **Fase 3.6** — Validación con *datasets* públicos (German Credit, Car Evaluation, Balance Scale, Breast Cancer WDBC, Iris, Blood Transfusion). ✅ Completada (3.6.a diseño, 3.6.b fetch + fixtures, 3.6.c tests de integración + informe, 3.6.d cierre documental). Suite 422/422.
- **Fase 3.6.e** — Modo no-bancario (terminología neutral + ejemplos + validación multi-dominio extensiva: marketing, ecología). Pendiente.
- **Fase 3.7** — Cierre Fase 3 + v1.0.0rc1 ✅ Completada (18/10/2026).
- **Fase 3.7.a** — Auditoría de seguridad ✅.
- **Fase 3.7.b** — Simetrización KS por pares ✅.
- **Fase 3.7.c** — min_child_weight expuesto ✅.
- **Fase 3.7.d** — Tests UCI ampliados ✅.
- **Fase 3.7.e** — Correcciones pre-release H1/H2/pd_floor ✅.
- **Fase 3.6.e** — Modo no-bancario extensivo: fuera del alcance de 1.0.0rc1, planificada para 1.1.0 o posterior.
- **Fase 4** — Reportes avanzados + export (SQL anidado, Python puro, reglas MD/JSON, doc automática)
- **Fase 5** — Capa MCP
- **Fase 6** — Scoring batch y champion-challenger
- **Fase 7** — IFRS 9 / ECL (staging + ECL = PD × LGD × EAD)

### Verificación manual de la GUI (13/10/2026)

La GUI se abrió en pantalla real por primera vez y se recorrió el flujo completo con el *dataset* sintético `data/credit_risk_dataset.csv`: cargar CSV, asistente de 4 pasos, entrenamiento CRT, evaluación OOS, gains table, matriz de clasificación con umbrales variables, export HTML y tema oscuro. Todos los pasos funcionaron correctamente y los valores numéricos mostrados coinciden con la corrida headless (PD raíz 6.65%, Gini OOS 0.4265, KS 0.3614). Se registraron 8 hallazgos de usabilidad y estética (H1 a H8) como deuda diferida. Ver `docs/roadmap.md` sección Deferred y `docs/audit_log.md` entrada del 13/10/2026.

---

## 4. Arquitectura

### Principio de sala limpia

- `backend_v3/` — capa analítica pura (0 imports Qt)
- `frontend_v3/` — capa de presentación (placeholder, sin lógica analítica)

### Estructura de directorios

```
TreeGov/
├── backend_v3/ # Capa analítica pura
├── frontend_v3/ # Capa de presentación PySide6
│ # (app, main_window, wizard, tree_view,
│ # metrics_panel, reports_panel, theme, i18n)
├── tests/ # Suite de tests (434 tests)
├── docs/ # Documentación bilingüe
│ ├── methodology.md
│ ├── design_decisions.md
│ ├── 3.1_design_multiclass.md
│ ├── 3.2_decisions_consolidated.md
│ ├── 3.3_design_population_categories.md
│ ├── 3.4_design_multiclass_crt_quest.md
│ ├── 3.6_design_public_datasets.md
│ ├── validation_results_3.6.md
│ ├── api.md
│ ├── roadmap.md
│ ├── philosophy.md
│ ├── philosophy.es.md
│ ├── estado_proyecto.md
│ ├── contexto_para_nueva_sesion.md
│ ├── prompt_para_asistente.md
│ └── audit_log.md
├── archive/ # Documentos y código históricos
├── data/ # Datasets (solo lectura, excluido de Git)
├── logs/ # Logs por corrida (excluido de Git)
├── treegov.py # Orquestador headless
├── treegov_gui.py # Entry point de la GUI (Fase 2)
├── pyproject.toml # Empaquetado (fuente oficial de dependencias)
├── requirements.txt # Mínimos de trabajo (transitorio)
├── opencode.json # Configuración del proyecto OpenCode
├── CONVENTIONS.md # Convenciones operativas para Aider
├── AGENTS.md # Instrucciones para agentes IA
├── README.md # README principal (inglés)
├── README.es.md # README en español
├── NOTICE.md # Aviso legal y atribución
├── LICENSE # Apache 2.0
├── .gitignore # Exclusiones de Git
├── .gitattributes # Normalización de line endings
├── .aiderignore # Exclusiones del repo-map de Aider
├── .aider.conf.example.yml # Plantilla de configuración de Aider
└── .treegovrules # Reglas de gobernanza para agentes IA
```

---

## 5. Decisiones arquitectónicas clave

| Decisión | Justificación |
|---|---|
| **GUI: PySide6** (no Streamlit) | Confidencialidad de datos bancarios: los datos no deben salir del escritorio del analista |
| **Caja blanca** (solo numpy/pandas/scipy) | Auditabilidad MRM: cada fórmula explícita con cita bibliográfica |
| **Gini = 2·AUC − 1** | Convención estándar en credit scoring (no confundir con Gini económico ni Gini = AUC − 0.5) |
| **Licencia Apache 2.0** | Permisiva, con cláusula de patentes, apta para uso bancario comercial |
| **Idioma de documentación** | Inglés por defecto (estándar *open source*); bilingüe README y philosophy; audit_log en español (histórico interno) |
| **Anti-leakage** | TrainOnlyImputer exclusivo sobre fold de entrenamiento |
| **OOT como archivo externo** | Nunca como partición aleatoria: validación temporal independiente |
| **GovernanceMode opcional (Fase 2.1)** | REGULATORY por defecto (Jeffreys + PD Floor, BCBS CRE 20.39); RESEARCH (PD cruda k/n sin floor) abre la herramienta a dominios no bancarios. Trazabilidad: el *fingerprint* del modelo etiqueta el modo efectivo (REGULATORY/RESEARCH/CUSTOM) |
| **Herramienta CLI fuera del .venv** | Aider instalado vía pipx con Python 3.11.9 independiente. Lección del 27/09: instalar herramientas CLI dentro del .venv del proyecto degradó numpy/scipy |
| **Proveedor de IA: Moonshot AI directo** | Migrado de NVIDIA NIM el 03/10/2026 por 504 recurrentes. Endpoint `https://api.moonshot.ai/v1`, costes $3/$15 por millón de tokens. Requiere `~/.aider.model.settings.yml` con `use_temperature: false` (Kimi K3 exige temperature=1). Cliente sigue siendo Aider (no OpenCode, no Kimi Code Desktop) |
| **`.gitattributes` con `-text`** | Previene mezcla de line endings (CRLF/LF) que genera diffs ruidosos (1218/1151 en lugar de 68 líneas reales). `-text` le dice a git "no normalices este archivo". Ver commit `7040046` |
| **Sala limpia de i18n** | Claves nombradas por estado (no por color). Tokens QSS semánticos en `theme.py` |
| **Documentación de fase cerrada: no se aplaza** | Regla de gobernanza (09/10/2026): al cerrar una sub-fase, audit_log + roadmap + estado_proyecto + documentos de contexto se actualizan en el mismo bloque de trabajo. Detalle en `docs/roadmap.md`, sección "Recorded architectural decisions" |

---

## 6. Auditorías y bugs resueltos

### Fase 0
- **Bug detectado:** `_group_sizes` con shape ambiguo cuando K=3 (target multiclase). Corregido con flag explícito.

### Fase 1.2
- **Bug crítico detectado en auditoría post-implementación:** confusión de cuadrantes `q_lr`/`q_rl` en el cálculo del agreement de surrogates (3 sitios). Corregido con reescritura usando cuadrantes explícitos.
- **Cobertura de tests ampliada:** 2 tests asimétricos + fixture exhaustivo limpio.

### Fase 1.3
- **FIX obligatorio:** `predict_leaf_assignment` con política `unseen_policy` (error/majority/exclude) para categorías nuevas en OOT.
- **FIX Media:** `gini_drop_alert(NaN) → "INDETERMINADO"` (evita reportar degradación indefinida como "sin alerta").
- **5 observaciones menores** aplicadas (tipado, numpy puro, RuntimeError, spec_order, oot_source).

### Fase 2.2
- **Bug detectado:** selección múltiple accidental en `TreeScene.select_node`. El nodo anterior permanecía seleccionado y `selected_node_id()` devolvía información errónea. Corregido con `self.clearSelection()` al inicio del método.

### Fase 2.3.d — bugs OpenCode documentados (histórico)
- GUI no genera mensaje final tras tool calls exitosas.
- Múltiples tool calls agotan cuota NVIDIA → 429.
- Notificación "Respuesta lista" sin haber ejecutado la tarea.
- **Diagnóstico completo en `docs/audit_log.md` (entrada 27/09/2026).**
- **Mitigación:** migración de OpenCode a Aider 0.86.2 el 27/09/2026.

### Fase 2.3.e.1 a 2.3.f
- **Incidente:** API key de NVIDIA pegada como placeholder literal en Aider → 403.
- **Incidente:** prompt de ~170 líneas a Aider → 504 timeout (2 intentos).
- **Lección:** prompts con bloques >100 líneas se trocean; excepción documentada para edición manual de docs.
- **Commit con mensaje engañoso** (`71978c5`): decía "add .aiderignore" pero solo commiteó `.gitignore`. Lección: los mensajes de commit deben reflejar contenido real.

### 03/10/2026 — Migración a Moonshot AI y normalización de line endings
- **Migración de proveedor de IA**: NVIDIA NIM → Moonshot AI directo por
  504 recurrentes. 3 iteraciones de configuración (401 de endpoint, 400 de
  temperature, éxito con `use_temperature: false`). Ver `audit_log.md`
  03/10/2026.
- **Line endings**: primer commit de la entrada de migración generó un diff
  de 1218/1151 líneas cuando solo había 68 reales. Causa: mezcla CRLF/LF al
  pegar en VS Code. Solución: `.gitattributes` con `* text=auto eol=lf` y
  excepción `docs/audit_log.md -text`. Ver `audit_log.md` 03/10/2026.
- **Configuración git global**: `core.autocrlf false` y `core.pager ""`
  (evita que la terminal se bloquee mostrando diffs largos).
- **Fase 2.4.c.2 — panel de reportes**: 3 sub-pasos (a: panel + i18n,
  b: cableado MainWindow, c: Export HTML + limpieza i18n + 7 tests).
  Documentada en `audit_log.md` con detalle de las 4 iteraciones de
  fix en `i18n.py` y las 2 excepciones de edición manual en VS Code.
- **Fase 2.4.b — backend de reportes**: `GainsTable` +
  `ClassificationMatrix` en `reporting.py`, 5 tests con valores
  verificados a mano (KS=220/589, AUC=10612.5/14725).  

Todos los bugs están registrados en `docs/audit_log.md` con trazabilidad numérica.

---

## 7. Suite de tests

| Módulo | Tests |
|---|---|
| statistics.py | 28 |
| chaid_engine.py | 26 |
| crt_engine.py | 27 |
| quest_engine.py | 35 |
| imputation.py | 5 |
| splitting.py | 11 |
| profiling.py | 3 |
| tree_builder.py | 38 |
| session_state.py | 87 |
| validation.py | 30 |
| pruning.py | 6 |
| stability.py | 18 |
| reporting.py | 27 |
| gui_smoke (frontend) | 9 |
| wizard (frontend) | 22 |
| tree_view (frontend) | 10 |
| metrics_panel (frontend) | 13 |
| e2e_mainwindow (frontend) | 9 |
| reports_panel (frontend) | 12 |
| e2e_reports (frontend) | 4 |
| uci_integration | 14 |
| **Total** | **434** |

**Ejecución:** `.\.venv\Scripts\python -m pytest tests -q` → 434/434 PASSED

**Filosofía de tests:** valores de referencia verificados a mano, con cita bibliográfica. No se aceptan tests de autoreferencia.

---

## 8. Estándares regulatorios cubiertos

- **Basilea (BCBS CRE 32.4)** — PD Floors regulatorios (0.05% / 5 bps
  para corporativos, bancos y retail; 0.03% / 3 bps o exención para
  soberanos).
- **EBA/GL/2017/16** — Validación de parámetros PD/LGD en modelos IRB
- **IFRS 9 / NIIF 9** — Staging, ECL, optimización de umbrales asimétricos
- **SR 11-7 / OCC 2011-12** — Model Risk Management (MRM)

---

## 9. Repositorios y recursos

| Recurso | Ubicación |
|---|---|
| GitHub | https://github.com/Marco-Rengel/treegov |
| PyPI | https://pypi.org/project/treegov/ |
| PyPI (versión actual) | https://pypi.org/project/treegov/1.0.0a6/ |
| Instalación | `pip install treegov` |
| Suite de tests | `.\.venv\Scripts\python -m pytest tests -q` |
| Demo headless | `.\.venv\Scripts\python treegov.py` |
| Benchmark N=1M | `.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42` |

---

## 10. Pendientes y decisiones abiertas

### Sesión documental — ✅ Bloque completo (24/09/2026)

- [x] Sincronizar entradas faltantes de Fase 1 y Fase 1.2 en `docs/audit_log.md` — Resuelto el 24/09/2026.
- [x] Enlace Filosofía → `docs/philosophy.md` en ambos READMEs — Resuelto el 24/09/2026.
- [x] Columna "Regulatory anchor" en la tabla de capacidades analíticas — Resuelto el 24/09/2026.
- [x] Aviso regulatorio reforzado con bloque visual (⚠️) — Resuelto el 24/09/2026.
- [x] Estado del proyecto visual con emojis/checklist en `roadmap.md` — Resuelto el 24/09/2026.
- [x] Bloque "Cómo se refleja esto en el diseño" en `philosophy.md` — Resuelto el 24/09/2026.

### Pendientes técnicos

- [x] **Decisión de proveedor de IA** — migrado a Moonshot AI directo el 03/10/2026. Ver `audit_log.md`.
- [x] **Herramienta activa de desarrollo** — OpenCode 1.19.0 + Kimi K3 vía Moonshot AI desde el 09/10/2026 (con Aider como respaldo en pipx). Ver `audit_log.md`.
- [x] **Fase 2.4** — Reportes + integración. Completada el 03/10/2026.
- [x] **Fase 3.0** — Cierre de zona gris documental + 4 parámetros canónicos. Completada el 04/10/2026.
- [x] **Fase 3.1** — Multiclase (6 sub-fases a-f). Completada el 09/10/2026.
- [x] **Fase 3.2** — Ponderación por muestra: Cerrada 10/10/2026 (8 sub-fases a-h, suite 346/346).
- [x] **Fase 3.3** — Categorías de población. Completada 11/10/2026. 5 sub-fases (a-e). Suite 384/384.
- [ ] **Fase 2.1.b** — CV scheme + guardrail runtime de imports backend.
- [x] **Publicar `treegov 1.0.0a1` en PyPI** — completado el 03/10/2026. URL: https://pypi.org/project/treegov/1.0.0a1/
- [ ] *Datasets* públicos (German Credit, UCI health/social) para validación multi-dominio (Fase 3).
- [ ] `requirements.txt` vs `pyproject.toml` — decidir fuente oficial.

### Pendientes diferidos / estructurales

- [ ] `CONTRIBUTING.md` en el repo (bloqueado por revisión legal).
- [ ] `docs/i18n/` para centralizar traducciones (cuando haya 5+ docs bilingües).
- [ ] Mnemonics `&` en menús GUI (Fase 2.3).
- [ ] QSettings persistencia de parámetros de gobernanza (Fase 2.1.b).
- [ ] QThread para entrenamiento largo (Fase 2.3+).
- [ ] Firma digital + instalador PyInstaller/Inno Setup (Fase 4).
- [ ] Licencia comercial paralela (análisis legal si se considera).
- [ ] Sub-fase de rediseño UX del asistente, visor del árbol y panel de reportes. 8 hallazgos H1 a H8. Ver `docs/roadmap.md` sección Deferred. No bloquea el desarrollo actual.
- [x] **Cierre de pendientes cosméticos de READMEs y philosophy** — commit 7334f65 (18/10/2026). Los tres ajustes cosméticos detectados el 17/10/2026 (mención CHAID Exhaustive, tabla solo en español, comillas tipográficas y título corregido) están cerrados. Sin cambios en backend_v3/ ni frontend_v3/; suite 422/422. Ver docs/audit_log.md entrada del 18/10/2026.
- [ ] Deuda post-rc1, target: 1.0.0 estable: D13 (KS/AUC/Gini del gains table binaria no ponderados con pesos no triviales; contradicción visible entre panel OOS/OOT y Reports/HTML para la misma partición).
- [ ] Deuda post-rc1, target: 1.0.0 estable: `pruning.py` no integrado en Session ni GUI, y no ponderado (criterio de poda usa conteos físicos mientras el crecimiento usa Gini ponderado). Incoherencia estadística entre crecimiento y poda.
- [ ] Deuda de trazabilidad: etiquetas de git `a1`–`a6` no creadas en el momento de la publicación. Identificar los commits correspondientes en audit_log y crear tags retroactivas si es posible. Tag `v1.0.0rc1` obligatorio en la próxima release.

### Decisiones de largo plazo

- [ ] **Distribución:** método de empaquetado, firma digital, canal.
- [ ] **Publicación del repo en GitHub:** pendiente de revisión legal antes de hacerlo público.

---
## 11. Cómo reconstruir el contexto en una nueva sesión

Si se inicia una conversación nueva (con un agente de IA o con un colaborador):

1. Leer en orden:
   - `README.md` (inglés) o `README.es.md` (español)
   - `.treegovrules` (reglas de gobernanza)
   - `CONVENTIONS.md` (convenciones para Aider)
   - `docs/methodology.md` (metodología matemática)
   - `docs/design_decisions.md` (decisiones de implementación)
   - `docs/3.1_design_multiclass.md` (diseño de Fase 3.1, en curso)
   - `docs/api.md` (API pública)
   - `docs/roadmap.md` (plan de fases)
   - `docs/audit_log.md` (histórico de decisiones)
   - `docs/contexto_para_nueva_sesion.md` (bootstrap)

2. Comando para retomar el desarrollo (OpenCode, herramienta activa):

```
cd "C:\Riesgos - copia\DecisionTree_Modeler"
.\.venv\Scripts\activate
git status
python -m pytest tests -q
opencode
```

(La autenticación con Moonshot AI ya está configurada vía
`opencode auth login`; no requiere variables de entorno. Para el
respaldo con Aider, ver `docs/contexto_para_nueva_sesion.md`.)

3. Primer mensaje sugerido al agente:

> "Retomamos TreeGov. Fases 0, 1, 1.2, 1.3, 2.0, 2.1, 2.2, 2.3, 2.4,
> 3.0, 3.1 (multiclase), 3.2 (ponderación por muestra), 3.3 (categorías
> de población), 3.4 (CRT y QUEST multiclase), 3.5.a, 3.5.b, 3.5.c y
> 3.5.d cerradas (Fase 3.5 completa). Suite 416/416. Próximo paso:
> Fase 3.6 (validación con datasets públicos) con OpenCode 1.19.0 +
> Kimi K3 vía Moonshot AI directo (key propia)."

---

## 12. Contacto y autoría

**Marco Rengel**
- Matemático con 16 años de experiencia en modelos de riesgo de crédito.
- Ex-analista en buró de crédito transnacional (2009-2016).
- Actualmente científico de datos en riesgos integrales en banca (desde 2023).
- GitHub: github.com/Marco-Rengel
- Email: marcrengel@gmail.com

---

*Documento mantenido tras cada fase cerrada. Fuente de verdad: el
repositorio en GitHub.*