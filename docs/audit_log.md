# Bitácora de Auditoría — TreeGov

Registro cronológico de decisiones arquitectónicas, hallazgos y correcciones durante el desarrollo de TreeGov.

---

### 20/09/2026 — Erradicación y esqueleto (Pasos 1-2)

**Estado**: Aprobado
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Antonio Rengel Calvopiña
**Artefactos**: backend_v3/, frontend_v3/, tests/, logs/

**Hallazgos**: Ninguno.

**Decisiones**:
- 7 rutas heredadas del proyecto anterior eliminadas (incluyendo archivos .py y carpetas de caché).
- Zonas protegidas verificadas: .venv/, data/, docs/, archive/, y el archivo de reglas heredado (movido a archive/legacy_docs/).

---

### 19/09/2026 — import_guard.py + log_config.py (Paso 3)

**Estado**: Aprobado
**Artefactos**: backend_v3/import_guard.py, backend_v3/log_config.py

**Hallazgos**: Ninguno.

**Identidades verificadas**:
- import_guard bloquea 7/7 librerías de caja negra (sklearn, scikit-learn, statsmodels, xgboost, lightgbm, catboost, sklearn.tree).
- log_config: doble handler (archivo + consola), ISO 8601 con offset correcto.

**Decisiones**:
- Logger renombrado de "dtm" a "treegov".

---

### 19/09/2026 — types.py (Paso 4)

**Estado**: Aprobado con 1 observación
**Artefactos**: backend_v3/types.py

**Hallazgos**:
| # | Severidad | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Baja | __repr__ de CRT | Duplicaba "gain=" cuando statistic_name ya lo anunciaba | Suprimido |

**Identidades verificadas**:
- SplitConfig frozen, hashable, con validación de invariantes en __post_init__.

---

### 19/09/2026 — statistics.py (Paso 5)

**Estado**: Aprobado
**Artefactos**: backend_v3/statistics.py, tests/test_statistics.py

**Hallazgos**: Ninguno.

**Identidades verificadas**:
- chi2 de Pearson: χ² = 20/3 para [[20,10],[10,20]].
- F ANOVA: F = 27 para [1,2,3], [4,5,6], [7,8,9].
- Brown-Forsythe: W = 0.8.
- Stirling: S(4,2)=7, S(5,2)=15, S(5,3)=25, S(20,3)=580606446.
- Kass ordinal: C(19,2)=171.

**Tests**: 13/13 por ambas vías (pytest + python directo).

---

### 19/09/2026 — chaid_engine.py (Paso 6)

**Estado**: Aprobado
**Artefactos**: backend_v3/chaid_engine.py, tests/test_chaid_engine.py

**Hallazgos**:
| # | Severidad | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | _group_sizes | Shape ambiguo cuando K=3 (target multiclase) | Flag explícito continuo |

**Identidades verificadas**:
- Convención Kass (1980) (p del par sobre subtabla 2×K, M sobre p global).
- Exhaustive incluye paso 0 (r=c, M=1) en la competencia del argmin.
- Cochran: fusión forzada activa.
- Exhaustivo: χ²=30.1266, F=1440, χ²=25.0788 (Cochran), χ²=25.8596 (K3).

**Tests**: 18/18. Rendimiento: 0.114s @1M.

---

### 20/09/2026 — crt_engine.py (Paso 7)

**Estado**: Aprobado tras remediación
**Artefactos**: backend_v3/crt_engine.py, tests/test_crt_engine.py

**Hallazgos (auditoría post-implementación)**:
| # | Severidad | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Alta | _best_agreement, _agreement_nominal, _metricas | Confusión de cuadrantes q_lr/q_rl. Agreement inflado en tablas 2×2 asimétricas. | Reescritura con cuadrantes explícitos |
| 2 | Media | tests surrogates | Cobertura solo con matrices simétricas (ocultaba el bug #1) | 2 tests asimétricos añadidos |
| 3 | Baja | _fixture_exhaustive | Cochran disparado en fixture, contaminando el camino exhaustivo | Nuevo fixture limpio |

**Bugs auto-detectados durante desarrollo**: 3 (_var_dI, ordinal simbólico, guard no-hashable).

**Identidades verificadas**:
- ΔI=0.5 (umbral binario), ΔI=1.0 (varianza), ΔI=49/225 (K=3 exhaustivo), ΔI=0.15 (heurística K>10), ΔI=64/225 (ordinal simbólico).
- Agreement=5/7 (surrogate asimétrico, flipped), agreement=0.6=majority → rechazado.

**Tests**: 15/15. Humo 200k: 0.056s.

---

### 20/09/2026 — quest_engine.py + imputation.py (Paso 8)

**Estado**: Aprobado tras remediación
**Artefactos**: backend_v3/quest_engine.py, backend_v3/imputation.py, tests/test_quest_engine.py, tests/test_imputation.py

**Hallazgos**:
| # | Severidad | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Alta | _mode | Bucle Python O(N) → cuello de botella con N=1M | value_counts() vectorizado (13ms @1M) |
| 2 | Media | _mode | Regresión de determinismo en empates con etiquetas no comparables | Fallback por orden de aparición secuencial |
| 3 | Media | _prepare | sorted(pd.unique(yd)) lanzaba TypeError críptico | Envuelto como ValueError con contexto |
| 4 | Baja | test Quest | Assertion sin sentido (p == p) | Reemplazado por rango válido [0,1] |

**Identidades verificadas**:
- F=54, W=72/7, QDA t=0, t=-ln(5/3)/2, t=(2/3)(√(4+3ln4)-1), t=0.25 (fallback), ΔGini=961/3600 (nominal).

**Tests**: 13 quest + 5 imputation = 18/18. Suite completa: 65/65.

---

### 20/09/2026 — treegov.py + benchmark_1m.py (Paso 9)

**Estado**: Aprobado tras 4 fixes
**Artefactos**: treegov.py, tests/benchmark_1m.py

**Hallazgos**:
| # | Severidad | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | treegov.py | mtime se verificaba después del print_report | Movido antes |
| 2 | Media | treegov.py | CHAID evalúa 3/8 predictores, no visible en consola | Nota al reporte |
| 3 | Media | benchmark | Métrica "s/predictor" inconsistente entre filas | Cambio a "segundos totales" + columna "evals" |
| 4 | Baja | stratified_split | assert desactivable con python -O | Convertido a ValueError |
| 5 | Trivial | benchmark | Constante _OBJETIVO_S_POR_PRED mal nombrada | Renombrada a _OBJETIVO_S_POR_EVAL |

**Identidades verificadas**:
- Demo: 4/4 motores con split válido. CHAID/EXH→tipo_empleo, CRT→ingreso_mensual (surrogate antiguedad), QUEST→ingreso_mensual.
- Benchmark 1M: peor caso 0.291 s/eval (objetivo < 1.5).

**Tests**: 65/65 suite completa. Demo exit 0.

---

### 20/09/2026 — Cierre de Fase 0

**Estado**: Fase 0 completada
**Acciones**:
- Reorganización documental: 6 archivos históricos movidos a archive/legacy_docs/ con cabecera.
- Creación de README.md, .treegovrules, docs/methodology.md, docs/audit_log.md, docs/filosofia.md.

**Resumen**: 4 motores (CHAID, CHAID_EXHAUSTIVE, CRT, QUEST) + imputación + orquestador + benchmark auditados y aprobados.

---

### 20/09/2026 — Flujo transaccional y estado cero (Fase 1)

**Estado**: Aprobado
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: backend_v3/splitting.py, backend_v3/profiling.py,
backend_v3/tree_builder.py, backend_v3/session_state.py,
tests/test_splitting.py, tests/test_profiling.py,
tests/test_tree_builder.py, tests/test_session_state.py.

**Hallazgos**: Ninguno bloqueante. El diseño fue auditado antes de
implementar (diseño → auditoría → código → verificación).

**Decisiones arquitectónicas**:
- Separación clean-room: `tree_builder.py` contiene TreeModel/TreeNode/
  TreeBuilder (construcción BFS determinista); `session_state.py` es la
  máquina de estados (EMPTY → DATA_LOADED → SPEC_FIXED → PARTITIONED →
  TRAINED), con atomicidad transaccional.
- Split train/test con Hamilton-Hare (largest remainder) para
  estratificación exacta sin sesgo de redondeo.
- Inferencia de tipos de predictor (nominal/ordinal/continuous) por
  cardinalidad (MAX_ORDINAL_CATS=20) — heurística documentada y auditable.
- `TreeBuilder` aplica la regla "min_child_size es piso absoluto": si
  alguna rama queda con menos filas que el mínimo, el split entero se
  rechaza (el nodo queda hoja). Sin fusión de respaldo.
- `Session` delega al backend; el frontend nunca lo toca directamente
  (sala limpia).

**Identidades verificadas**:
- `stratified_split` reprodujo proporciones exactas en fixtures
  controlados (largest remainder con empates resueltos determinísticamente).
- `TreeBuilder` con C&RT sobre fixture simple generó árbol conocido
  (raíz con split en x<=t, hojas 1 y 2 con n exactos).
- `Session` respetó transiciones legales y lanzó ValueError en ilegales.

**Tests**: 22 nuevos. Suite total: 87/87.

---

### 20/09/2026 — Evaluación OOS + poda coste-complejidad (Fase 1.2)

**Estado**: Aprobado tras remediación
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: backend_v3/validation.py, backend_v3/pruning.py,
tests/test_validation.py, tests/test_pruning.py.

**Hallazgos (auditoría post-implementación)**:
| # | Sev | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | validation.py | Métricas retornadas como tuplas sueltas | Contenedor OOSMetrics (frozen) |
| 2 | Media | validation.py | `predict_pd` abortaba en categorías nuevas (OOT real) | Política `unseen_policy` (error/majority/exclude) |
| 3 | Media | pruning.py | Secuencia de poda con descendientes "fantasma" tras podar | `_eliminar_descendientes` recursivo |
| 4 | Baja | validation.py | Dependencia de pandas en cálculo de mid-ranks | Vectorización numpy pura |

**Bugs auto-detectados durante desarrollo**:
- ROC/KS/PR-AUC con empates: acumulados al inicio del bloque en lugar del final (el umbral cubre TODO el grupo de empate).

**Decisiones arquitectónicas**:
- Métricas OOS: Gini canónico (2·AUC−1) vía Wilcoxon-Mann-Whitney con
  mid-ranks; KS; Hosmer-Lemeshow; Brier + BSS; ROC puntos completos;
  PR-AUC como Average Precision escalonado (Davis & Goadrich 2006).
- Poda coste-complejidad de Breiman (1984): secuencia de α con empates
  simultáneos (todos los nodos del mínimo, convención Breiman); el
  `prune(alpha)` siempre parte del modelo original (idempotencia).
- Re-indexado BFS tras poda: TreeModel válido, hojas nuevas con
  `leaf_reason="podado"`.
- Módulo autocontenido: `validation.py` no depende de engines, solo de
  TreeModel.

**Identidades verificadas**:
- Gini = 1 con separación perfecta; Gini = 0 con modelo nulo.
- PSI: fórmula correcta, verificada contra cálculo a mano.
- Poda con α manual produjo secuencia de pasos exacta (α₁, α₂...) y
  re-indexado correcto.
- `prune(α)` no apila podas sobre podas previas (idempotencia).

**Tests**: 20 nuevos. Suite total: 107/107.

---

### 22/09/2026 — stability.py + extensiones de session_state (Fase 1.3)

**Estado**: Aprobado tras 2 fixes
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: backend_v3/stability.py, backend_v3/session_state.py,
backend_v3/validation.py (predict_leaf_assignment), tests/test_stability.py,
docs/methodology.md §8.5, docs/api.md.

**Hallazgos (auditoría post-implementación)**:
| # | Sev | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | OOTReport.metrics | Tipado como object | OOSMetrics vía TYPE_CHECKING |
| 2 | Media | gini_drop_alert | NaN se reportaba como "none" | "INDETERMINADO" |
| 3 | Baja | covariate_csi | Series |= ndarray frágil | numpy puro |
| 4 | Baja | load_oot | sorted() innecesario | spec_order |
| 5 | Baja | load_oot | assert desactivable con -O | RuntimeError |
| 6 | Baja | evaluate_oot | narrativa sin granularidad de origen | oot_source="external-file" |

**Identidades verificadas**:
- PSI: 0 (identidad), 0.0875469 (cambio moderado), 0.8788898 (UNSTABLE), 9.2093 (bin vacío con clip eps).
- Gini Drop: 0.5 crítico / 0.25 preventivo / 0.1 none / None-NaN INDETERMINADO.
- e2e: categoría nueva en variable del árbol -> 20/60 filas excluidas registradas; PSI con bin `<UNSEEN>`; CSI con bin `<OTHER>`; verificación temporal con time_col; fuga temporal -> ValueError.

**Tests**: 12 nuevos. Suite total: 119/119.

---

### 23/09/2026 — Mejora del README (bilingüe)

**Estado**: Aprobado
**Revisor**: Marco Rengel
**Artefactos**: README.md, README.es.md

**Cambios aplicados** (feedback de colega auditor externo):
- Resumen ejecutivo no técnico al inicio (facilita lectura a no técnicos).
- Tabla de capacidades analíticas (capacidad / referencia / características
  clave) reemplazando la lista en bullets.
- Timeline visual de fases (tabla con estados Completada / En progreso /
  Planificada).
- Aviso regulatorio reforzado con la frase "No está apto todavía para
  producción bancaria" — protege al autor y clarifica el estado ante
  reguladores.
- Consistencia visual de headings (## principales, ### subsecciones).
- Cita Siddiqi (2006) añadida a referencias académicas.
- Sección "Regulatory references" separada de "Academic references".
- Estructura del repositorio actualizada (14 módulos backend).
- Suite de tests (119/119) en el header.
- Sección "Contributions" deliberadamente omitida (pendiente de decisión
  legal sobre el contrato laboral actual antes de aceptar PRs externos).

**Justificación**: el README es la primera impresión del proyecto ante
auditores, reguladores, colaboradores y reclutadores. La mejora responde
a feedback de auditor externo y refuerza la filosofía de "gobernanza
primero". Los cambios se aplicaron a ambos READMEs (EN y ES) para evitar
divergencia documental.

---

### 23/09/2026 — Esqueleto GUI + i18n bilingüe (Fase 2.0)

**Estado**: Aprobado tras 1 micro-ajuste
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: treegov_gui.py, frontend_v3/{__init__,app,i18n,
main_window,theme}.py, frontend_v3/resources/styles.qss,
tests/test_gui_smoke.py, docs/roadmap.md.

**Hallazgos (auditoría post-implementación)**:
| # | Sev | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Baja | main_window.py | Status bar mostraba "light"/"dark" crudo en lugar de etiqueta traducida | tr(f'menu_view_theme_{name}') |
| 2 | Trivial | styles.qss | Comentario $TOKENS interpretado como placeholder por string.Template | Comentario reescrito sin $ |

**Bugs auto-detectados durante desarrollo**:
- FIX 1 aplicado: 3 claves i18n del menú Model (Train / Evaluate OOS /
  Load OOT Cohort).
- 2 claves i18n extra detectadas honestamente por el agente: toggles de
  paneles (menu_view_toggle_left/right). Total: 29 claves por idioma.
- Bug propio capturado por los tests: $TOKENS en QSS rompía el render.

**Decisiones arquitectónicas**:
- QSS con string.Template y tokens $X (evita colisión con llaves {} de
  QSS). Fail-fast en palette/template mismatch.
- i18n con diccionario Python plano (no Qt Linguist .ts/.qm): auditable
  en texto plano, cambio de idioma en caliente con retranslate_ui().
- Widgets construidos vacíos; retranslate_ui() es única fuente de verdad
  de textos (llamada al final de __init__).
- Excepthook condicional a platformName() != "offscreen" (evita modal
  colgado en CI).
- TREEGOV_GUI_AUTOQUIT_MS: mecanismo de auto-quit para CI headless.
- Session importada solo bajo TYPE_CHECKING (sala limpia).

**Identidades verificadas**:
- Suite: 128/128 PASSED (119 previos + 9 nuevos: 6 smoke + 3 i18n).
- Guardrail AST: import numpy en frontend_v3/ → FAILED (bloqueo OK).
- treegov_gui.py offscreen con auto-quit → exit 0, log limpio.
- treegov.py backend → exit 0, sin regresión.

**Documentación adicional**: OBS 1 (mnemonics "&") y OBS 3 (guardrail
runtime de imports backend) registradas en docs/roadmap.md para fases
posteriores.

---

### 23/09/2026 — Wizard transaccional + Governance Mode (Fase 2.1)

**Estado**: Aprobado tras remediación de 2 hallazgos de implementación
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/wizard.py, frontend_v3/main_window.py,
frontend_v3/i18n.py, backend_v3/types.py, backend_v3/tree_builder.py,
backend_v3/session_state.py, backend_v3/profiling.py,
tests/test_wizard.py, tests/test_session_state.py,
tests/test_tree_builder.py, tests/test_gui_smoke.py, docs/{roadmap,
methodology, api, estado_proyecto}.md.

**Hallazgos (auditoría post-implementación)**:
| # | Sev | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | wizard.py | El spec pedía `QWizard.WizardOption.NoHelpButton`: NO existe en Qt 6 (existe `HaveHelpButton`; el botón Help está oculto por defecto) | Documentado en código; micro-ajuste resuelto por omisión (sin llamada) |
| 2 | Media | tests/test_wizard.py | El slot programático `QWizard.next()` no invoca el override `validateCurrentPage` (verificado con espía); el gate REAL del usuario es el botón Next deshabilitado vía isComplete/completeChanged | Test de navegación reescrito sobre el estado del botón (lo observable); override mantenido como defensa en profundidad |
| 3 | Baja | state_proyecto.md §7 | Tabla de tests desactualizada: decía session_state 10 / stability 12; los reales eran 13+6=19 y 9 | Tabla regenerada con `pytest --collect-only` |
| 4 | Media | wizard.py _refresh_summary | "Engine:" y el modo de gobernanza crudos (sin tr()) en el resumen del Step 4 | tr() + 3 claves i18n nuevas (step4_summary_engine, step4_govmode_*_short) |
| 5 | Baja | wizard.py ModelWizard | language_bus sin disconnect al cerrar (referencia viva a bound method) | closeEvent con disconnect defensivo (try/except RuntimeError/TypeError) |

**Bug preexistente detectado y corregido durante esta fase**:
`TreeBuilder.__init__` ejecutaba `int(max_depth)` incondicional, así que
`max_depth=None` (modo grow_full) lanzaba TypeError. El docstring lo
prometía desde Fase 1.2 (alimenta la poda coste-complejidad de
pruning.py) pero nunca se había ejercido. Corregido con validación
explícita de None + test_grow_full_max_depth_none.

**Decisiones arquitectónicas**:
- GovernanceMode (types.py): BANKING (Jeffreys + PD Floor, BCBS CRE 20.39;
  defecto) / RESEARCH (PD cruda k/n, sin floor). La UI solo emite los dos
  modos; combinaciones intermedias vía API se etiquetan CUSTOM.
- params_fingerprint incluye governance_mode/apply_jeffreys/pd_floor: dos
  árboles con distinta gobernanza NUNCA comparten fingerprint.
- Deltas backend (sala limpia): `describe_dataset()` (lectura pura),
  `fix_spec(predictors=...)` (filtro dentro del backend),
  `train(motor_por_nombre)` (factory interna), `reset_to_data_loaded()`
  (sin re-IO del CSV). El frontend jamás instancia motores ni toca
  PredictorType/DataFrame.
- LanguageBus (QObject singleton en i18n.py): única vía de retraducción
  en caliente; el wizard es NO modal justamente para permitir el cambio
  de idioma/tema mientras está abierto.
- Regla espejo CHAID en Step 2: los predictores [CONT] se deshabilitan en
  la UI cuando el motor es CHAID (el backend los rechaza por contrato).
- Diálogo de error suprimido bajo QT_QPA_PLATFORM=offscreen (CI jamás se
  cuelga en un modal).

**Identidades verificadas**:
- Research: hoja pura k=0 -> pd_final == 0.0 exacto (sin Jeffreys ni floor);
  Banking: pd_final = max(0.0003, (k+0.5)/(n+1)).
- fingerprint BANKING != RESEARCH != CUSTOM (mismo dataset/parámetros).
- grow_full: max_depth=None alcanza profundidad >= 4 sin TypeError.
- train("CRT") == train(CrtEngine()) (mismo fingerprint, factory OK).
- Reset conserva el DataFrame en caché (mismo objeto) y limpia artefactos.
- Test micro-ajuste 3: combo target preserva currentText/currentData tras
  cambio de idioma en caliente.
- Guardrail AST: import numpy en frontend_v3/ -> FAILED (bloqueo OK).
- treegov_gui.py offscreen con auto-quit -> exit 0, log limpio.
- treegov.py backend -> exit 0, sin regresión.
- Suite: 148/148 PASSED (128 previos + 6 session + 4 builder + 9 wizard
  + 1 grow_full).

---

### 25/09/2026 — Cierre Fase 2.2: Visor interactivo de árbol

**Estado**: Aprobado tras 1 hallazgo de implementación
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/tree_view.py, frontend_v3/main_window.py,
frontend_v3/i18n.py, tests/test_tree_view.py

**Hallazgos (auditoría post-implementación)**:
| # | Sev | Ubicación | Descripción | Resolución |
|---|---|---|---|---|
| 1 | Media | tree_view.py (TreeScene.select_node) | Selección múltiple accidental: al seleccionar un nodo nuevo, el anterior permanecía seleccionado (Qt permite multiselección por defecto). `selected_node_id()` devolvía el nodo equivocado y el HUD mostraba información desactualizada. Detectado por `test_e2e_mainwindow`. | Añadido `self.clearSelection()` al inicio de `select_node()`. La selección es ahora exclusiva y determinista. |

**Identidades verificadas**:
- `test_tree_view.py` 10/10 PASSED en WSL (Python 3.14.4, pytest 9.1.1).
- `test_e2e_mainwindow`: selección nodo 1 → nodo 0 → HUD muestra Predictor (antes fallaba).
- `scipy 1.18.1` importa sin errores en WSL (bloqueo de DLLs en Windows resuelto).
- `treegov_gui.py` offscreen con auto-quit → exit 0.
- `treegov.py` backend headless → 4/4 splits, exit 0.

**Tests**: 10 nuevos. Suite total: 158/158.

---

### 26/09/2026 — Fase 2.3.c: esqueleto del panel OOS/OOT

**Estado**: Aprobado sin hallazgos
**Modelo**: Nemotron 3 Ultra 550B A55B (high, vía NVIDIA NIM)
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/metrics_panel.py (nuevo), frontend_v3/main_window.py, tests/test_metrics_panel.py (nuevo), tests/test_gui_smoke.py, tests/test_tree_view.py, docs/audit_log.md, docs/roadmap.md

**Hallazgos**: Ninguno bloqueante. Se corrigió un SyntaxWarning ("\S" inválido) en test_metrics_panel.py mediante escape correcto.

**Identidades verificadas**:
- MetricsPanel se construye sin errores (offscreen).
- retranslate_ui funciona al cambiar idioma vía language_bus.
- MainWindow tiene 3 pestañas (Welcome | Tree | OOS/OOT).

**Tests**: 3 nuevos + 2 existentes ajustados (assert de 2→3 pestañas en test_layout_structure y test_e2e_mainwindow). Suite total: 161/161.

---

### 27/09/2026 — Migración a Python 3.11 y consolidación de entorno Windows

**Estado**: Aprobado sin hallazgos de código
**Modelo**: N/A (cambio de infraestructura)
**Revisor**: Marco Rengel
**Artefactos**: `.gitignore`, `AGENTS.md`, `docs/contexto_para_nueva_sesion.md`, `.venv/` (recreado), `.venv_3.14_backup/` (respaldo)

**Motivación**:
El proyecto fue diseñado y documentado para Python 3.11 (`pyproject.toml`: `requires-python = ">=3.11"`), pero los entornos de desarrollo terminaron en Python 3.14 (versión por defecto del sistema operativo). Aunque la suite pasaba en 3.14, existía un riesgo latente de incompatibilidad futura con librerías del stack científico (numpy, scipy, pandas, PySide6) y una discrepancia entre documentación y realidad — inaceptable bajo la filosofía MRM del proyecto.

**Acciones ejecutadas**:
- Instalación de Python 3.11.9 vía `winget` en Windows.
- `.venv/` (Windows) renombrado a `.venv_3.14_backup/` (respaldo reversible).
- Nuevo `.venv/` creado con Python 3.11.9.
- Dependencias reinstaladas: numpy 2.4.6, pandas 3.0.6, scipy 1.17.1, PySide6 6.11.2, pyarrow 25.0.1, openpyxl 3.1.5, pytest 9.1.1.
- `.gitignore` refinado: `.venv_linux/` y `.venv_3.14_backup/` ahora ignorados explícitamente (antes dependían de reglas internas de cada venv, frágil ante copias/ediciones).
- `AGENTS.md` actualizado: sección "Entorno" alineada con la realidad; comandos Windows (PowerShell) y WSL (bash) separados.
- `docs/contexto_para_nueva_sesion.md` actualizado: fecha, conteo de tests (161/161), rutas OpenCode para Windows y WSL, tabla de problemas ampliada (variant, cuota NVIDIA 429, modelos descontinuados, git push desde WSL).

**Identidades verificadas**:
- Suite completa en Windows + Python 3.11.9: **161/161 PASSED** (primera corrida 15.90s, cachés fríos).
- `git check-ignore -v` confirma que los 3 venvs (`.venv/`, `.venv_linux/`, `.venv_3.14_backup/`) están ignorados por reglas explícitas del `.gitignore` del proyecto.
- WSL permanece operativo con Python 3.14.4 y `.venv_linux/` como respaldo.

**Decisión arquitectónica**:
- **Windows nativo + Python 3.11.9** = plataforma principal.
- **WSL + Python 3.14.4** = respaldo (por si Windows vuelve a bloquear scipy vía WDAC/Smart App Control).
- **Compatibilidad declarada**: 3.11+ (ver `pyproject.toml`).

**Tests**: 161/161. Sin regresiones.

---

### 27/09/2026 — Fase 2.3.d (parcial): reporting backend implementado

**Estado**: Aprobado parcialmente. Tests pendientes por bugs de OpenCode.
**Modelo**: Kimi K3 vía NVIDIA NIM (max reasoning)
**Revisor**: Marco Rengel
**Artefactos**: `backend_v3/reporting.py` (nuevo), `backend_v3/session_state.py` (modificado)

**Motivación**:
Orquestador backend que expone el DTO plain-Python de métricas OOS/OOT para el panel GUI.

**Decisiones arquitectónicas**:
- `reporting.py` usa `asdict()` para aplanar OOSMetrics/OOTReport sin importar validation/stability en runtime.
- `TYPE_CHECKING` guard evita ciclo session_state ↔ reporting.
- `build_oos_oot_report(st: SessionState)` recibe el dataclass, no Session.
- `Session.get_oos_oot_report()` es pass-through (línea 169).
- DTO con claves "oos"/"oot", sin dataclasses propias.

**Identidades verificadas**:
- reporting.py: 21 líneas.
- Session.get_oos_oot_report(): línea 169 de session_state.py.
- Suite: 161/161 PASSED.

**Hallazgos (bugs OpenCode, severidad creciente)**:
| # | Sev | Descripción |
|---|---|---|
| 1 | Media | GUI no genera mensaje final tras tool calls exitosas. |
| 2 | Alta | Múltiples tool calls (Grep/Read) agotan cuota NVIDIA → 429 con prompts medianos. |
| 3 | **Crítica** | Notificación "Respuesta lista" sin haber ejecutado la tarea (test_reporting.py no se creó). |

**Mitigación adoptada**:
- Verificación obligatoria con `Select-String`/`Get-Item`/`pytest` tras cada tarea de OpenCode.
- Prompts quirúrgicos con referencias exactas al código; evitar que el agente haga Grep.
- **A largo plazo**: evaluar alternativa (Aider, Cline) en sesión dedicada.

**Pendiente**:
- tests/test_reporting.py (bloqueado por bug #3).
- Integración de metrics_panel.py con Session.get_oos_oot_report().

**Referencias**: OpenCode issues #32400, #42605.

---

### 27/09/2026 — Diagnóstico final: incompatibilidad OpenCode + NVIDIA NIM + Kimi K3

**Estado**: Cerrado operativamente. Causa exacta pendiente de atribución interna.
**Modelo**: N/A (diagnóstico de infraestructura)
**Revisor**: Marco Rengel
**Colaboración externa**: Gemini Pro y Copilot (razonamiento profundo) validaron el análisis.

**Motivación**:
Tras dos semanas con bugs intermitentes (congelamientos, 429, ausencia de mensaje final tras tool calls), se ejecutó un diagnóstico estructurado con reinstalación limpia, pruebas controladas y comparación de proveedores.

**Hipótesis descartadas empíricamente**:
| # | Hipótesis | Resultado |
|---|---|---|
| 1 | Plugins interfiriendo | ❌ Bug persiste sin plugins. |
| 2 | Duplicación de AGENTS.md | ❌ Bug persiste sin duplicación. |
| 3 | Cuota diaria NVIDIA agotada | ❌ curl directo responde OK. |
| 4 | Instalación corrupta de OpenCode | ❌ Reinstalación limpia reproduce el bug. |
| 5 | Problema del proyecto TreeGov | ❌ Bug no aparece en sandbox vacío. |
| 6 | Incompatibilidad 1.18.31/1.18.32 | ❌ Bug en ambas versiones. |
| 7 | Dos API keys NVIDIA activas | ❌ OpenCode usa una sola. |

**Evidencia empírica decisiva (misma sesión, mismo proyecto, mismo prompt)**:
| Proveedor · Modelo | Tool calls | Mensaje final | Tiempo |
|---|---|---|---|
| NVIDIA NIM · Kimi K3 | ✅ Ejecutados | ❌ Ausente | ~70 s |
| Google AI Studio · Gemini 3.8 Flash | ✅ Ejecutados | ✅ Completo y estructurado | ~14 s |

**Formulación rigurosa del hallazgo (adoptada tras revisión externa)**:
> La causa está localizada en la compatibilidad del ciclo de herramientas entre OpenCode 1.18.32 y Kimi K3 servido por NVIDIA NIM. La evidencia disponible no permite distinguir entre (a) el formato de respuesta de NIM, (b) la continuidad conversacional requerida por Kimi K3, o (c) el procesamiento de esa respuesta por OpenCode.

**Respaldos en issues de OpenCode/GitHub (verificados por Copilot)**:
- "Add graceful fallback for missing response.id from NVIDIA NIM"
- "NVIDIA NIM kimik2.5 returns numeric tool call IDs causing 'expected id to be a string' error"
- "GLM-5 via NVIDIA NIM emits malformed MCP tool JSON"
- "Bug: NVIDIA API models hang indefinitely during generation"
- "Nvidia NIM API hangs for DeepSeek v4 reasoning models without chat_template_kwargs"

Los issues confirman que la compatibilidad de tool calling entre OpenCode y NVIDIA NIM ha tenido problemas reales, dependientes del modelo, en identificadores, estructura de respuestas, parámetros específicos y streaming.

**Estrategia adoptada**:
- **Gemini 3.8 Flash (Google AI Studio)**: proveedor principal para desarrollo diario (crear/editar código, ejecutar tests, refactorizar, documentación).
- **Kimi K3 (NVIDIA NIM)**: segunda opinión para revisión conceptual, **preferentemente sin tool calls**. Prompts del tipo "no modifiques archivos, revisa esta propuesta y devuelve riesgos/supuestos/casos límite".

**Alerta de privacidad (crítica)**:
- El nivel gratuito de Google AI Studio puede usar el contenido para mejorar sus productos.
- Los NVIDIA API Trial Terms definen el servicio como prueba, no apto para producción.
- **Regla para TreeGov**: nunca enviar datos bancarios reales, credenciales, contratos, ni información interna a ninguna capa gratuita. Solo datasets públicos (German Credit, UCI) o sintéticos. El proyecto es open source y no maneja datos reales, por lo que la estrategia es viable.

**Verificación obligatoria**:
- No confiar en la notificación "Respuesta lista" de OpenCode.
- Verificar siempre con `Get-Item`, `Select-String`, `git status` o `pytest` tras cada tarea.

**Pendiente (no bloqueante)**:
- Atribución exacta de la causa (requeriría leer el código de OpenCode y NIM).
- Issue reproducible puede reportarse en el repo de OpenCode con la evidencia recogida (opcional, contribución a la comunidad).

### 27/09/2026 — Fase 2.3.e.1 abortada; diagnóstico OpenCode + Gemini

**Estado**: Abortada sin cambios en el repo.
**Modelo**: Gemini 3.8 Flash (Google AI Studio, intento fallido).
**Revisor**: Marco Rengel

**Motivación**:
Intento de normalizar los strings de semáforo en `stability.py`
(`INDETERMINADO` → `UNDETERMINED`, `critico/preventivo/none` →
`CRITICAL/WARNING/NONE`) como primer paso de la Fase 2.3.e.

**Cronología del fallo**:
1. Gemini ejecutó correctamente las fases de exploración (solo lectura):
   Read stability.py, Grep "INDETERMINADO" en session_state.py (4 matches),
   Read session_state.py (offset 490, limit 30), Read test_stability.py,
   Grep "gini_drop_alert" (22 matches), "traffic_light" (16 matches).
2. Antes de emitir cualquier Write/Edit, OpenCode abortó con:
   `Requests ending with a model turn are not supported.`
3. Reintento manual ("continue") → bucle `gemini is way too hot right now`,
   sin progreso durante minutos.
4. Interrupción con Ctrl+C. Ningún archivo fue modificado.

**Verificación post-fallo**:
- `git status` → working tree clean.
- `python -m pytest tests -q` → 161/161 PASSED.
- Sin cambios en backend, frontend ni docs.

**Hallazgo**:
Error de protocolo en OpenCode 1.18.32, no del proveedor. Gemini completa
la exploración (tool calls de solo lectura funcionan) pero la transición a
escritura queda bloqueada. Esto es **distinto** al bug documentado de
Kimi K3 + NVIDIA NIM (entrada 27/09/2026, misma fecha). Ambos afectan al
ciclo de tool calls; el de Kimi impedía el mensaje final, el de Gemini
impide la escritura tras exploración.

**Decisión**:
Migrar de OpenCode a **Aider** con NVIDIA NIM. Motivos:
- Aider no comparte el mismo código de orquestación de tool calls.
- Aider hace commits automáticos (desactivables con `--no-auto-commits`),
  coherente con la disciplina MRM del proyecto.
- Aider falla de forma visible: si no escribe, no lo dice.

**Suite**: 161/161 (sin regresión, sin cambios).

**Referencias**: observación local, sin issues externas asociadas.

### 27/09/2026 — Incidencia y decisión: stack de librerías tras instalar Aider

**Estado**: Aprobado con verificación empírica.
**Modelo**: N/A (decisión de entorno).
**Revisor**: Marco Rengel

**Motivación**:
`pip install aider-chat` en el `.venv` del proyecto degradó dependencias
fijadas con `==` por Aider:
- numpy  2.4.6  → 1.26.4
- scipy  1.17.1 → 1.15.3
- pygments 2.21.0 → 2.19.2
- packaging 26.3 → 26.0

**Decisión**:
Mantener las versiones degradadas. Justificación:
- Python permanece en 3.11.9 (intérprete intacto).
- Congelar la rama mayor de numpy/scipy reduce el coste de mantenimiento
  frente a actualizaciones futuras (los cambios entre ramas mayores son
  los que rompen; dentro de una rama, la compatibilidad es fuerte).
- El proyecto no corre en producción ni expone superficie sensible; el
  coste de no actualizar es bajo.

**Verificación empírica**:
- `python -m pytest tests -q` → **167/167 PASSED** con numpy 1.26.4 +
  scipy 1.15.3 + pandas 3.0.6 + PySide6 6.11.2.

**pyproject.toml**:
No requiere cambios. Los rangos `>=` declarados (numpy>=1.24,
scipy>=1.10) admiten tanto las versiones nuevas como las degradadas.

**Lección para el futuro**:
Las herramientas CLI (Aider, linters, formatters) NO deben instalarse en
el `.venv` del proyecto. Contaminan el stack verificado. Considerar venv
separado (`~/.venv_aider/`) si surgen más herramientas.

**Observación lateral (no bloqueante)**:
`packages = ["backend_v3"]` empaqueta solo la capa analítica, pero las
dependencias incluyen PySide6. Si el paquete PyPI no debe incluir la GUI,
conviene revisar si PySide6 pertenece a `dependencies` o a
`optional-dependencies`. Decidir en la fase de publicación.

**Tests**: 167/167. Sin regresión.

### 27/09/2026 — Fase 2.3.e.1: normalización del alfabeto de semáforos

**Estado**: Aprobado con verificación empírica.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: backend_v3/stability.py, backend_v3/session_state.py,
tests/test_stability.py, docs/methodology.md, .gitignore

**Motivación**:
Los semáforos de `traffic_light()` y `gini_drop_alert()` mezclaban
idioma y caso: `INDETERMINADO` (español, mayúsculas), `critico`/`preventivo`/
`none` (español, minúsculas), `STABLE`/`MODERATE`/`UNSTABLE` (inglés,
mayúsculas). La Fase 2.3.e requiere que el frontend consuma estos strings
sin mapa ad-hoc para i18n.

**Cambios aplicados**:
- `traffic_light`: `INDETERMINADO` → `UNDETERMINED` (docstring actualizado).
- `gini_drop_alert`: `INDETERMINADO` → `UNDETERMINED`, `critico` →
  `CRITICAL`, `preventivo` → `WARNING`, `none` → `NONE` (docstring ampliado
  con los umbrales).
- Docstring de `GiniDropReport` normalizado.
- Comentario en `Session._drop` (session_state.py) actualizado.
- `tests/test_stability.py` (cabecera + `test_gini_drop_alert_manual`)
  actualizado con los nuevos strings.

**Migración de herramienta (OpenCode → Aider)**:
Documentada en entrada previa (27/09/2026, Fase 2.3.e.1 abortada).

**Observaciones operativas de Aider (no bloqueantes)**:
1. Warning "Unknown context window size" para `nvidia_nim/moonshotai/kimi-k3`:
   Aider asume 8K tokens cuando Kimi K3 tiene 1M. Provoca:
   - `summarizer unexpectedly failed for all models` en una sesión.
   - Un intento fallido de reescritura completa del archivo (descartado por
     Aider antes de aplicar).
      Mitigación aplicada: entrada en `~/.aider.model.metadata.json`
      con `max_input_tokens: 1048576` y `max_output_tokens: 131072`.
      Verificado: Aider arranca sin warning; repo-map subió de 1024 a 4096
      tokens (mejor contexto de proyecto).

2. **Atribución actualizada del bug de tool calls**: Aider 0.86.2 + Kimi K3
   + NVIDIA NIM completa ciclos de tool calls sin pérdida de mensaje final.
   Evidencia empírica de que el componente dominante del fallo previo era
   **OpenCode 1.18.32** (no NIM ni Kimi K3). La formulación previa ("no
   atribuible a una sola capa") se estrecha: el cliente era el factor
   principal. Los bugs de OpenCode se manifestaban más frecuentemente a
   medida que crecía el tamaño del contexto (Fase 2.3.d: 50-100K tokens
   por tool call vs. Fase 0: 5-10K).

**Identidades verificadas**:
- `traffic_light(float("nan"))` → `"UNDETERMINED"`.
- `gini_drop_alert(None)` y `gini_drop_alert(float("nan"))` → `"UNDETERMINED"`.
- Umbrales preservados: `0.40` → `WARNING` (no `CRITICAL`, sigue el `>` estricto),
  `0.20` → `NONE` (sigue el `>` estricto).
- Cero cambios en lógica; solo strings y docstrings.

**Tests**: 167/167 PASSED.

**Referencias**: entrada previa "Fase 2.3.e.1 abortada; diagnóstico OpenCode
+ Gemini" (misma fecha).

### 28/09/2026 — Migración de Aider a pipx

**Estado**: Aprobado.
**Modelo**: N/A (infraestructura).
**Revisor**: Marco Rengel
**Artefactos**: AGENTS.md, `.aider.conf.example.yml` (nuevo), .gitignore

**Motivación**:
Aider vivía en el `.venv/` del proyecto, lo que degradó numpy (2.4.6 → 1.26.4)
y scipy (1.17.1 → 1.15.3) el 27/09. Aunque la suite verificó 167/167 con las
versiones degradadas, contaminar el entorno verificado del proyecto es deuda
técnica.

**Acciones**:
- Instalado `pipx` (Python 3.14 del sistema).
- Instalado Aider con `pipx install --python 3.11 aider-chat` (Python 3.11.9
  del sistema, no el del proyecto).
- Creado `.aider.conf.example.yml` (versionado) con plantilla de configuración.
- Añadida excepción `!.aider.conf.example.yml` en `.gitignore`.

**Incidente durante la migración**:
El primer intento con Python 3.14 falló: scipy 1.15.3 no tiene wheel prearmada
para esa versión y el build local requiere compilador Fortran (no instalado).
Solución: forzar Python 3.11 en pipx.

**Estado del `.venv/` del proyecto**:
No fue modificado por la migración. Conserva numpy 1.26.4 + scipy 1.15.3
(degradadas), con verificación 167/167. La decisión del 27/09 de mantenerlas
se mantiene vigente; se evaluará actualización en una sesión futura si surge
motivo.

**Beneficios**:
- `aider.exe` disponible globalmente (sin activar `.venv`).
- Contaminación del entorno del proyecto prevenida a futuro.
- Plantilla `.aider.conf.example.yml` versionada para colaboradores.

**Tests**: 167/167 (verificado tras la migración).

### 29/09/2026 — Fase 2.3.e.2: claves i18n por estado

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/i18n.py

**Motivación**:
La Fase 2.3.e.1 normalizó el alfabeto de semáforos del backend
(`STABLE`/`MODERATE`/`UNSTABLE`/`UNDETERMINED`/`CRITICAL`/`WARNING`/`NONE`),
pero las claves i18n del frontend seguían nombradas por color
(`status_green`/`status_yellow`/`status_red`). Un nombre por color
envejece mal si se cambia la paleta. La Fase 2.3.e.2 renombra las claves
por estado y añade las 4 que faltaban para cubrir el alfabeto completo.

**Cambios aplicados** (en cada bloque "en" y "es"):
- Renombradas: `status_green` → `status_stable`,
  `status_yellow` → `status_moderate`, `status_red` → `status_unstable`.
- Añadidas: `status_undetermined`, `status_critical`, `status_warning`,
  `status_none`.
- Valores de texto preservados: `STABLE`/`MODERATE`/`UNSTABLE` (EN);
  `ESTABLE`/`MODERADO`/`INESTABLE` (ES). Nuevos:
  `UNDETERMINED`/`CRITICAL`/`WARNING`/`NONE` (EN);
  `INDETERMINADO`/`CRÍTICO`/`PREVENTIVO`/`SIN ALERTA` (ES).

**Verificación previa**:
`Get-ChildItem` sobre `backend_v3/` y `frontend_v3/` confirmó que las
claves viejas solo existían en `i18n.py`. Ninguna otra parte del código
las referenciaba, por lo que el renombrado no rompe contratos.

**Paridad EN/ES**:
Ambos bloques contienen las mismas 7 claves de estado. Convención del
proyecto respetada.

**Aviso de Aider (no aplicado)**:
Aider sugirió añadir `metrics_panel.py` al chat por si referenciaba las
claves viejas. Se rechazó con `n` — verificado previamente que no las usa.
Comportamiento del agente: correcto (auditoría proactiva).

**Tests**: 167/167 PASSED.

### 29/09/2026 — Fase 2.3.e.3: tokens QSS semánticos de estado

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/theme.py, frontend_v3/resources/styles.qss

**Motivación**:
Tras 2.3.e.1 (alfabeto de semáforos) y 2.3.e.2 (claves i18n por estado),
el panel OOS/OOT necesita poder pintar badges visuales de estado
(verde/ámbar/rojo/gris) sin hardcodear colores en `metrics_panel.py`.
Los tokens semánticos permiten que los colores cambien con el tema
(light/dark) sin tocar el código del panel.

**Cambios aplicados**:
- `theme.py`: 4 tokens nuevos en cada paleta (`STATUS_OK`, `STATUS_WARN`,
  `STATUS_CRIT`, `STATUS_UNKNOWN`). Valores Material Design 700 en light,
  400 en dark — contraste AA garantizado.
- `styles.qss`: 4 selectores nuevos al final
  (`QLabel[status="ok"|"warn"|"crit"|"unknown"]`) con `color: $STATUS_*`
  y `font-weight: bold`.

**Verificación de fail-fast**:
`render_stylesheet('light')` y `render_stylesheet('dark')` ejecutados
manualmente sin ValueError. Ambos retornan QSS completo (1477 caracteres).
La validación de `theme.py` (tokens del template ausentes en la paleta)
no se activó, confirmando que ambos bloques quedaron consistentes.

**Verificación de no-regresión**:
Suite completa 167/167 PASSED.

**Comportamiento de Aider**:
El agente detectó y comunicó proactivamente que "los tokens $STATUS_*
ya existen en ambas paletas, por lo que la validación fail-fast seguirá
pasando" — auditoría correcta sin haber sido solicitada.

**Tests**: 167/167 PASSED.

### 29/09/2026 — Fase 2.3.e.4: MetricsPanel funcional

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/metrics_panel.py, tests/test_metrics_panel.py

**Motivación**:
El esqueleto de 2.3.c era un placeholder sin lógica. Tras 2.3.e.1
(alfabeto backend), 2.3.e.2 (claves i18n por estado) y 2.3.e.3 (tokens
QSS semánticos), ya están disponibles todos los insumos para que el panel
consuma el DTO de `Session.get_oos_oot_report()` y renderice las métricas
con badges de estado.

**Cambios aplicados**:
- `metrics_panel.py`: reescrito como consumidor del DTO.
  - Constantes `_STATUS_TO_QSS` y `_STATUS_TO_I18N` mapeando los 7 códigos
    del alfabeto backend a propiedades QSS (`ok`/`warn`/`crit`/`unknown`)
    y a claves i18n.
  - Helper `_fmt(value)`: "—" si None, `%.4g` si float, `str` si no.
  - `set_report(dto)` como API pública; `refresh()` reconstruye contenido.
  - Secciones OOS (n_test, gini, ks, brier, brier_skill, hl_p) y OOT
    (PSI flag, Gini Drop alert_oot, peor CSI por valor).
  - Badges con `setProperty("status", qss_status)` — el QSS de 2.3.e.3 los
    colorea automáticamente sin hardcodear colores.
  - Fallthrough seguro: código desconocido → `status_undetermined` + QSS
    `unknown`.
- `tests/test_metrics_panel.py`: 6 tests nuevos.
  - `set_report(None)` y DTO vacío → placeholder.
  - OOS solo, OOT solo (verifica 3 badges con `statuses == ["crit","crit","warn"]`).
  - Fallthrough de código desconocido.
  - Cobertura completa del alfabeto en ambos mapas.

**Verificación de sala limpia**:
`metrics_panel.py` solo importa `PySide6.QtCore`, `PySide6.QtWidgets` y
`frontend_v3.i18n`. Cero numpy/pandas/scipy.

**Comportamiento de Aider**:
Propuso correctamente NO tocar tests en el Prompt 1 (los rompía el cambio
de `_label`), esperando autorización. En el Prompt 2 ejecutó exactamente
el spec de tests sin añadir ni quitar.

**Tests**: 173/173 PASSED (167 previos + 6 nuevos).

### 29/09/2026 — Fase 2.3.e.5: cableado MainWindow ↔ MetricsPanel

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/main_window.py

**Motivación**:
El MetricsPanel ya era funcional (2.3.e.4), pero MainWindow no lo
conectaba: los menús Model > Evaluate OOS y Load OOT Cohort seguían
deshabilitados con tooltip "Available in Phase 2.3", y el panel nunca se
poblaba automáticamente tras entrenar. Esta fase cablea el ciclo
completo.

**Cambios aplicados (7 puntos en main_window.py)**:
1. Eliminada la constante `_TT_PHASE23`.
2. Actions `_act_evaluate_oos` y `_act_load_oot`: sin tooltip, conectados
   a sus handlers `_on_evaluate_oos` / `_on_load_oot`.
3. `_refresh_session_indicator()`: habilita ambos actions solo si el
   Session está en estado TRAINED.
4. `_on_new_wizard()`: añade `self._metrics_panel.set_report(None)` al
   resetear la sesión.
5. `_on_wizard_finished()`: tras entrenar, llama
   `self._metrics_panel.set_report(self._session.get_oos_oot_report())`.
6. Nuevo handler `_on_evaluate_oos()`: llama `Session.evaluate_oos()`,
   refresca el panel, cambia a la pestaña OOS/OOT.
7. Nuevos `_on_load_oot()` + `_load_oot_pipeline()`: pide CSV al usuario,
   carga, evalúa, refresca el panel.

**Comportamiento de Aider**:
Prompt con 7 cambios referenciados por bloque y línea exacta. Aider los
aplicó en una sola pasada sin consultas adicionales. Sin falsos positivos
en el diff.

**Tests**: 173/173 PASSED (los tests anteriores no ejercitaban los
handlers nuevos; eso quedó cubierto en 2.3.f).

---

### 29/09/2026 — Fase 2.3.f: tests E2E + cierre de Fase 2.3

**Estado**: Aprobado.
**Modelo**: N/A (autoría manual por el asistente estratégico; ver
lección operativa al final).
**Revisor**: Marco Rengel
**Artefactos**: tests/test_e2e_mainwindow.py (nuevo)

**Motivación**:
Los 173 tests previos no ejercitaban el flujo end-to-end entre
MainWindow, Session y MetricsPanel. En particular, los handlers nuevos
de 2.3.e.5 (`_on_evaluate_oos`, `_on_load_oot`) no tenían cobertura.

**Cambios aplicados**:
- Nuevo archivo `tests/test_e2e_mainwindow.py` con 5 tests E2E:
  1. `test_e2e_load_csv_enables_actions`: cargar CSV habilita wizard y
     train; los actions OOS/OOT siguen deshabilitados hasta entrenar.
  2. `test_e2e_train_enables_oos_oot_actions`: tras entrenar, evaluate_oos
     y load_oot pasan a enabled.
  3. `test_e2e_evaluate_oos_refreshes_panel`: disparar
     `_on_evaluate_oos` puebla la sección OOS del panel y cambia la
     pestaña activa.
  4. `test_e2e_load_oot_via_mocked_dialog`: con `QFileDialog.getOpenFileName`
     mockeado, cargar cohorte OOT produce badges en el panel (PSI +
     Gini Drop).
  5. `test_e2e_new_wizard_resets_panel`: reabrir el wizard limpia el
     panel (`set_report(None)`).

**Identidades verificadas**:
- 5/5 tests E2E en verde.
- Suite completa: 178/178 PASSED (173 previos + 5 nuevos).
- CSV sintético determinista (seed=42), target `default = 1_{edad>=40}`.
- Mock de QFileDialog confirma que el handler no abre diálogo real en
  entorno offscreen.

**Cierre de Fase 2.3**:
Con 2.3.f se cierra la fase completa (2.3.a a 2.3.f). El panel OOS/OOT
está operativo end-to-end: carga datos, entrena, evalúa OOS, carga OOT,
evalúa, y renderiza badges con colores semánticos del tema activo.

**Lección operativa (docs editing)**:
Durante 2.3.e.2 a 2.3.e.5 parte de la documentación (audit_log, roadmap,
contexto_para_nueva_sesion, prompt_para_asistente) se editó manualmente
en VS Code en lugar de pasar por Aider. Esto generó 3 incidentes menores:
triplicación del `.gitignore`, indentación rota en `audit_log`, línea
duplicada en `contexto_para_nueva_sesion`. Además creó asimetría con el
resto de la bitácora (que atribuye los cambios a Aider).

**Regla adoptada**:
La edición de docs pasa por Aider+Kimi con prompts del tipo "inserta
exactamente este bloque al final de X, no modifiques nada más". Las
excepciones son:
- Creación inicial de documentos de bootstrap largos (>200 líneas): se
  redacta como borrador y se pega a mano en VS Code, verificando con
  `git diff` que el archivo quedó íntegro.
- Cambios triviales de 1 línea que requieran verificación manual
  inmediata.
- Indisponibilidad del servidor NIM (errores 504/timeout), como ocurrió
  al cierre de esta sesión. Documentar la excepción en la propia entrada.

**Tests**: 178/178 PASSED.

---

### 30/09/2026 — Optimización del flujo de trabajo con Aider

**Estado**: Aprobado.
**Modelo**: N/A (configuración de infraestructura).
**Revisor**: Marco Rengel
**Artefactos**: CONVENTIONS.md (nuevo), .aiderignore (nuevo),
.aider.conf.yml (local, no versionado)

**Motivación**:
Tras la sesión del 29/09, se identificaron tres mejoras que reducen la
fricción con Aider sin cambiar el flujo de trabajo:
1. Repetir reglas del proyecto en cada prompt es propenso a omisiones y
   alarga los prompts (mayor riesgo de 504).
2. Aider indexa carpetas que no se tocan (`archive/`, `logs/`, `data/`,
   venvs), gastando tokens de repo-map.
3. No existía un documento compacto de convenciones operativas (el
   `.treegovrules` es más amplio y conceptual).

**Cambios aplicados**:
- `CONVENTIONS.md` (nuevo, ~56 líneas): reglas operativas que Aider lee
  automáticamente. Incluye sala limpia, verificación obligatoria,
  convenciones de comentarios, caja blanca, límite de prompts, y flujo
  de trabajo.
- `.aiderignore` (nuevo): excluye del repo-map las carpetas `archive/`,
  `logs/`, `data/`, `.venv*/`, `.opencode*/`, `.pytest_cache/`,
  `__pycache__/`, `.aider.tags.cache.v4/`, `*.log`.
- `.aider.conf.yml` (local): añadida línea `read: CONVENTIONS.md` para
  que Aider cargue las convenciones como contexto de solo lectura.

**Verificación**:
- Aider arranca con `Readonly: CONVENTIONS.md` en el encabezado.
- El conteo de archivos del repo pasó de 69 a 64 (los excluidos por
  `.aiderignore` ya no aparecen).
- Sin warnings de context window ni de env vars.

**Incidentes menores durante la sesión**:
1. El commit `71978c5` decía "add .aiderignore with gitignore exception"
   pero solo commiteó `.gitignore` (el archivo `.aiderignore` seguía
   ignorado por el patrón `.aider*`). El commit `da09676` corrigió la
   parte factual, pero el mensaje del `71978c5` queda desactualizado en
   el historial.
2. La API key se pegó accidentalmente en un prompt de Aider (por confundir
   el prompt `>` con PowerShell). La key quedó visible en el historial
   local de Aider. Recomendación: regenerar la key en NVIDIA.

**Lección operativa**:
Los mensajes de commit deben reflejar el contenido REAL del commit. Si
al hacer `git add` Git advierte que un archivo está ignorado, el commit
NO debe hacerse hasta resolver la excepción — el mensaje no puede
anticipar lo que se "iba a" añadir.

**Excepción al flujo de docs por Aider**:
Esta entrada se redactó manualmente en VS Code (no vía Aider) por
indisponibilidad del servidor NVIDIA NIM: dos intentos consecutivos con
Aider devolvieron 504 timeout, seguidos de una respuesta corrupta
(`!!!!!` en lugar del diff). La regla adoptada el 29/09 contempla
explícitamente esta excepción.

**Tests**: 178/178 PASSED (sin cambios en código).

---

### 30/09/2026 — Sincronización de READMEs tras cierre de Fase 2.3

**Estado**: Aprobado.
**Modelo**: N/A (edición manual en VS Code).
**Revisor**: Marco Rengel
**Artefactos**: README.md, README.es.md

**Motivación**:
Los READMEs quedaron desactualizados tras el cierre de Fase 2.3
(29/09/2026). Mantenían el conteo de tests en 167/167 y la tabla de fases
con 2.3 "In progress" y 2.4 "Planned". Además, la estructura del
repositorio no reflejaba los archivos nuevos `CONVENTIONS.md` y
`.aiderignore` añadidos ese mismo día.

**Cambios aplicados** (en ambos idiomas):
- Conteo de tests: 167/167 → 178/178 (header y cierre).
- Tabla de fases: Fase 2.3 "In progress" → "Completed"; Fase 2.4
  "Planned" → "In progress".
- Estructura del repositorio: añadidas entradas para `CONVENTIONS.md` y
  `.aiderignore`.

**Excepción al flujo de docs por Aider**:
Edición manual en VS Code por indisponibilidad del servidor NVIDIA NIM
(504 recurrentes durante la sesión). Misma excepción documentada en la
entrada "Optimización del flujo de trabajo con Aider" del 30/09/2026.

**Tests**: 178/178 PASSED (sin cambios en código).

---

### 01/10/2026 — Fase 2.4.a: esqueleto estructural del panel de reportes

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía NVIDIA NIM (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: frontend_v3/i18n.py, frontend_v3/reports_panel.py
(nuevo), frontend_v3/main_window.py, tests/test_gui_smoke.py,
tests/test_metrics_panel.py, tests/test_tree_view.py

**Motivación**:
Primera sub-fase de Fase 2.4 (Reportes + integración). Se crea el
andamio estructural: pestaña nueva "Reports", panel placeholder, claves
i18n y ajuste de tests. La lógica real de gains table y matriz de
clasificación va en 2.4.b y 2.4.c.

**Cambios aplicados**:
1. `i18n.py`: 2 claves nuevas por idioma (`tab_reports_title`,
   `reports_no_model`). Paridad EN/ES estricta.
2. `reports_panel.py` (nuevo): clase `ReportsPanel(QWidget)` con
   estructura espejo de `MetricsPanel` — QLabel centrada, retraducción
   en caliente vía `language_bus`, `refresh()` como placeholder.
3. `main_window.py`: import de `ReportsPanel`, instancia como cuarta
   pestaña, `setTabText(3, tr("tab_reports_title"))` en `retranslate_ui`.
4. Tests: `count() == 3` → `count() == 4` en `test_gui_smoke.py` y
   `test_tree_view.py`. Renombrado `test_mainwindow_has_three_tabs` a
   `test_mainwindow_has_four_tabs` con assert nuevo de `tab_reports_title`.

**Lecciones operativas sobre Aider + NVIDIA NIM (críticas)**:

Durante esta sesión se identificaron dos patrones de fallo concretos:

1. **Prompts con código literal grande fallan.** Enviar un prompt con
   ~40 líneas de código Python literal para "crear archivo nuevo" produjo
   3 fallos consecutivos (respuestas basura `!!!!!` o 504). El mismo
   prompt reescrito **en prosa sin código literal** funcionó a la
   primera. Regla nueva: prompts a Aider describen estructura en prosa,
   no pegan código.

2. **Prompts con múltiples archivos + múltiples cambios fallan.**
   Un prompt de 3 cambios en 3 archivos distintos falló con 504. El
   mismo trabajo dividido en **3 sesiones separadas de 1 archivo cada
   una** funcionó cada vez, respondiendo en menos de 1 minuto. Regla
   nueva: un prompt = un archivo (excepto cuando el cambio es
   intrínsecamente multi-archivo y pequeño).

3. **`Create new file?` vs `Add file to the chat?`.** Confusión del
   revisor: responder `n` a `Create new file?` cancela la creación del
   archivo (no la pregunta "¿añadir al contexto?"). La pregunta
   `Create new file?` debe responderse `y`.

**Comportamiento correcto del agente**:
Aider detectó correctamente que no necesitaba cargar `i18n.py` ni
`metrics_panel.py` como contexto en varias sesiones (el prompt ya
describía la estructura), reduciendo tokens innecesarios.

**Tests**: 178/178 PASSED (los 3 tests que fallaban por conteo de
pestañas se corrigieron a 4).

---

### 03/10/2026 — Migración de NVIDIA NIM a Moonshot AI directo

**Estado**: Aprobado tras 3 iteraciones de configuración.
**Modelo**: Kimi K3 vía Moonshot AI (plataforma internacional, NOVASCENT/Singapur).
**Revisor**: Marco Rengel
**Artefactos**: `.aider.conf.yml` (local, no versionado),
`~/.aider.model.metadata.json`, `~/.aider.model.settings.yml` (nuevo),
variable de entorno `MOONSHOT_API_KEY`.

**Motivación**:
NVIDIA NIM (free tier) presentó 504 recurrentes durante las sesiones del
30/09 y 01/10/2026, confirmando que el servicio de prueba no es fiable
para uso sostenido. Se evaluó la migración a la API de pago de Moonshot AI
(creadores de Kimi K3) y se cargaron $20 el 04/10/2026 (factura 2846-0745,
NOVASCENT PRIVATE LIMITED, Singapur).

**Decisión de cliente**:
Se mantiene Aider 0.86.2 como cliente (no se vuelve a OpenCode ni se
migra a Kimi Code Desktop). Motivos:
- El bug del 27/09/2026 era de OpenCode 1.18.32, no del proveedor.
  Cambiar de API no arregla el cliente.
- Kimi Code Desktop es un agente de propósito general con GUI; no ofrece
  el control granular de prompts que exige la gobernanza MRM de TreeGov.
- Aider tiene `auto-commits: false`, historial auditable y
  `CONVENTIONS.md` cargado como contexto readonly.

**Cambios aplicados**:
- `.aider.conf.yml`: `model` cambiado de `nvidia_nim/moonshotai/kimi-k3`
  a `moonshot/kimi-k3`. Eliminada la línea `openai-api-base` (LiteLLM
  conoce el endpoint de Moonshot por defecto). Resto del archivo sin
  cambios.
- `~/.aider.model.metadata.json`: añadida entrada `openai/kimi-k3` con
  costes reales ($3/M input, $15/M output) y contexto 1M. La entrada
  previa de NIM se preservó como respaldo.
- `~/.aider.model.settings.yml` (nuevo): entrada `moonshot/kimi-k3` con
  `use_temperature: false` y `edit_format: whole`. Motivo: Kimi K3
  (modelo de razonamiento) rechaza cualquier temperatura distinta de 1.
- Variable de entorno: `$env:MOONSHOT_API_KEY` en lugar de
  `NVIDIA_NIM_API_KEY`.

**Iteraciones de diagnóstico**:
1. `openai/kimi-k3` + `openai-api-base`: error 401. LiteLLM enrutaba a
   api.openai.com en lugar de Moonshot.
2. `moonshot/kimi-k3` sin settings: error 400
   `invalid temperature: only 1 is allowed for this model`.
3. `moonshot/kimi-k3` + `use_temperature: false`: éxito.

**Identidades verificadas**:
- `curl https://api.moonshot.ai/v1/models` devolvió 4 modelos
  (`kimi-k3`, `kimi-k2.7-code`, `kimi-k2.6`, `kimi-k2.7-code-highspeed`).
  Kimi K3 con 1M de contexto y `think_efforts` en low/high/max.
- YAML de settings validado con `yaml.safe_load`.
- JSON de metadata validado con `ConvertFrom-Json`.
- Aider arranca sin warning de context window. Prueba de humo respondida
  sin error 401 ni 400. Coste de la prueba: $0.02.

**Consecuencia operativa**:
La regla de "un prompt = un archivo" del 01/10/2026 (motivada por los
504 de NIM) se mantiene por claridad de diffs, pero se suaviza la
restricción de tamaño: al eliminar la capa NIM, los 504 desaparecen.
Prompts de hasta ~150 líneas de prosa son viables. La disciplina de
verificación (`git diff` + `pytest`) no cambia.

**Tests**: 178/178 PASSED (sin cambios en código).

---

### 03/10/2026 — Normalización de line endings y `.gitattributes`

**Estado**: Aprobado.
**Modelo**: N/A (decisión de infraestructura git).
**Revisor**: Marco Rengel
**Artefactos**: `.gitattributes` (nuevo, versionado),
`docs/audit_log.md` (reescrito limpio).

**Motivación**:
Al añadir la entrada anterior ("Migración de NVIDIA NIM a Moonshot AI
directo") mediante VS Code, git reportó un diff de 1218 inserciones y
1151 borrados cuando en realidad solo se añadieron ~68 líneas. Causa:
mezcla de terminadores de línea (CRLF heredado del historial del archivo
vs. LF introducido por VS Code con la opción `files.eol: "\n"`).

**Cómo detectarlo** (referencia para futuras sesiones):
Síntoma: un commit cuyo `--stat` muestra cientos o miles de líneas
borradas y añadidas en un archivo que solo recibió un bloque pequeño.
Diagnóstico rápido: `git diff -w --stat <archivo>` — el flag `-w` ignora
cambios de whitespace (incluyendo line endings). Si con `-w` el diff se
reduce a un número pequeño (~N líneas reales), el ruido es de line endings.
Segundo diagnóstico: `git ls-files --eol <archivo>` muestra el line ending
del índice (`i/`), del working tree (`w/`) y los atributos aplicados
(`attr/`).

**Solución adoptada**:
Crear `.gitattributes` en la raíz del repo con dos reglas:
1. `* text=auto eol=lf` — por defecto, todos los archivos se guardan en el
   repo con LF (estándar moderno, evita futuras mezclas).
2. `docs/audit_log.md -text` — excepción para este archivo: `-text` le dice
   a git "no normalices los saltos de línea al hacer add/commit". Esto
   evita que un archivo con historial CRLF se reescriba entero al primer
   commit, generando un diff ruidoso de transición.

**Iteraciones**:
1. Intento inicial con `docs/audit_log.md text eol=crlf` → mismo diff
   ruidoso (1218/1151). La opción `eol=crlf` normaliza al vuelo y detecta
   el archivo entero como cambiado si el índice estaba en estado distinto.
2. `git config --global core.autocrlf false` → necesario pero no
   suficiente por sí solo.
3. `.gitattributes` con `-text` para el archivo específico → diff limpio
   (68 inserciones, 1 borrado) en el commit final.

**Configuración de entorno aplicada** (referencia):
- `git config --global core.autocrlf false` — evita que git convierta
  line endings automáticamente según la plataforma.
- `git config --global core.pager ""` — desactiva el pager (less) al
  ejecutar `git diff`. Sin esto, la terminal se queda "trabada" mostrando
  el diff en modo lectura hasta pulsar `q`.

**Lecciones operativas para futuras sesiones**:
1. Antes de un `git commit`, verificar qué hay en staging con
   `git status`. Si hay archivos adicionales de un `git add` previo, hacer
   `git reset HEAD <archivo>` para no mezclar cambios no relacionados en
   el mismo commit.
2. Al introducir `.gitattributes` en un repositorio con historial previo,
   preferir `-text` (no normalizar) para archivos con terminadores
   distintos al estándar nuevo, en lugar de `eol=crlf` o `eol=lf`.
3. No asumir que un comando sugerido por un asistente IA en un chat se ha
   ejecutado sin verificarlo con `git config --get` o similar.
4. Cualquier diff anómalamente grande (~1000+ líneas) en un archivo de
   texto plano debe tratarse como sospecha de problema de line endings
   antes de commitear.

**Tests**: 178/178 PASSED (sin cambios en código).

---

### 03/10/2026 — Fase 2.4.b: backend de reportes (GainsTable + ClassificationMatrix)

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: `backend_v3/reporting.py` (ampliado, commit `aa3b8fb`),
`tests/test_reporting.py` (5 tests nuevos, commit `511dbce`).

**Motivación**:
Segunda sub-fase de Fase 2.4 (Reportes + integración). Proveer al
frontend (2.4.c) de un DTO de reportes que cubra:
- Gains table por hoja (`by="leaf"`, default) o por bucket
  (`by="bucket"`, `n_buckets` parametrizable).
- Matriz de clasificación con threshold parametrizable.
Ambos operan sobre `leaf_assignment` (int, -1 = fila excluida),
`y` (0/1), y el `TreeModel` ya entrenado.

**Arquitectura decidida**:
- Cálculo on-demand desde `Session` (Opción B descartada A/C por
  contaminar `SessionState` con datos por fila). El frontend consumirá
  `Session.get_gains_table()` / `Session.get_classification_matrix()`
  cuando 2.4.c lo implemente.
- `reporting.py` recibe `leaf_assignment` + `y` + `model` como argumentos
  (no `X` ni DataFrame). La asignación la hace `validation.predict_leaf_assignment`
  una sola vez, aguas arriba. `reporting.py` no reimplementa routing.
- Sin pandas: solo numpy + stdlib. Sala limpia respetada.
- `TreeModel` bajo `TYPE_CHECKING`: cero imports runtime de `tree_builder`
  desde `reporting.py`.

**Cambios aplicados**:

`backend_v3/reporting.py` (367 inserciones, 4 borrados):
- 3 dataclasses frozen: `GainsRow`, `GainsTableResult`,
  `ClassificationMatrix`.
- Helper privado `_validated_routed`: valida y filtra filas enrutables
  (`leaf_assignment >= 0`); devuelve `(routed_mask, leaf_ids, y_routed)`.
- Helper privado `_discrimination_metrics`: reimplementación mínima de
  KS/AUC/Gini sobre PD por fila, con las mismas fórmulas que
  `validation.compute_oos_metrics` (KS por bloques de empate con
  acumulación al final; AUC por Wilcoxon-Mann-Whitney con mid-ranks;
  Gini = 2·AUC − 1). Devuelve `None, None, None` si falta una clase.
- `build_gains_table(model, leaf_assignment, y, *, by="leaf",
  n_buckets=10, tie="preserve", seed=None)`: agrupa filas por hoja o
  bucket, calcula Cum/Decum, `bad_rate`, `lift_cum`, y devuelve
  `GainsTableResult` con KS/AUC/Gini recomputados.
- `build_classification_matrix(leaf_assignment, y, pd_per_leaf, *,
  threshold=0.5)`: matriz 2×2 con precision, recall, F1 y
  `bad_capture_rate` (alias explícito de recall, nomenclatura de buró).

`tests/test_reporting.py` (205 inserciones, 2 borrados):
- Fixture de 3 hojas (PDs 0.1/0.3/0.6, 250 filas, 95 bads).
- 5 tests: gains por hoja con Cum/Decum verificados a mano, gains por
  bucket con tie="preserve" (frontera snap), gains por bucket con
  tie="random" (reproducibilidad con seed), classification matrix a dos
  thresholds, exclusión de filas con `assign == -1`.

**Identidades verificadas a mano**:
- Fixture: n_total=250, n_bad=95, n_good=155, bad_rate_global=0.38.
- KS = 60/95 − 40/155 = 220/589 ≈ 0.373514.
- AUC = 10612.5/14725 ≈ 0.720713.
- Gini = 2·AUC − 1 ≈ 0.441426.
- Bucket preserve: frontera b=125 se desplaza a 150 (fin del bloque
  de empates PD=0.3) → B01 con 150 filas, B02 con 100.
- ClassificationMatrix threshold=0.5: tp=60, tn=115, fp=40, fn=35,
  precision=0.6, recall=60/95, f1=72/117≈0.615385.
- ClassificationMatrix threshold=0.2: tp=90, tn=45, fp=110, fn=5,
  precision=0.45, recall=90/95, f1≈0.610169.

**Hallazgos durante la implementación**:
- El asistente corrigió dos valores `f1` del diseño original
  (0.61514 → 0.615385 y 0.61016 → 0.610169). Eran typos del revisor
  humano; la fórmula estándar 2PR/(P+R) da los valores corregidos.
- El asistente detectó que la firma real de `build_classification_matrix`
  es `(leaf_assignment, y, pd_per_leaf, *, threshold)` — orden distinto
  al asumido en el prompt inicial. Corregido tras añadir `reporting.py`
  al contexto de Aider. Lección: cuando el diseño de tests depende de
  firmas exactas, el archivo bajo prueba debe estar en el contexto del
  agente.
- Los tests usan `pytest.approx` para comparaciones float; el archivo
  original no importaba pytest (usaba `==` sobre valores enteros).
  Añadido.

**Tests**: 183/183 PASSED (178 previos + 5 nuevos).

**Referencias**: `docs/roadmap.md` (sección Fase 2.4),
`docs/estado_proyecto.md` (sección 3).

---

### 03/10/2026 — Fase 2.4.c.1: métodos de reporte en Session

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2, whole edit format).
**Revisor**: Marco Rengel
**Artefactos**: `backend_v3/session_state.py` (commit `795f163`),
`tests/test_session_state.py` (commit `9586bf3`).

**Motivación**:
Primera sub-fase de 2.4.c. Exponer `GainsTable` y `ClassificationMatrix`
al frontend sin violar la sala limpia (`frontend_v3/` no puede importar
numpy ni `reporting.py`). Se sigue el patrón ya establecido por
`get_oos_oot_report`: métodos en `Session` devuelven dict plano vía
`asdict` (o `None` si no hay modelo).

**Arquitectura decidida**:
- Sin caché de `leaf_assignment` en 2.4.c.1: se recalcula on-demand
  desde la caché interna de `Session` (`_X_train` / `_X_test` / `_X_oot`).
  Si el rendimiento lo exige en el futuro, se añade caché explícita.
- `unseen_policy` por partición: `"error"` para train (todas las filas
  deben enrutar; si no, es un bug), `"exclude"` para oos/oot (categorías
  nuevas son legítimas y deben contarse en `n_excluded`).
- Helper privado `_routed_partition(partition)`: valida tree presente,
  partición válida, y caché poblada. Devuelve `(X, y, unseen_policy)`.
- `SessionState` no se toca: sigue frozen, sin datos por fila.

**Cambios aplicados**:

`backend_v3/session_state.py` (96 inserciones, 2 borrados):
- Import de `reporting` ampliado (`build_classification_matrix`,
  `build_gains_table`).
- Import de `dataclasses` ampliado (`asdict`).
- Import nuevo `from typing import Any`.
- Helper `_routed_partition` justo antes de `get_oos_oot_report`.
- Método `get_gains_table(*, partition, by, n_buckets, tie, seed)`.
- Método `get_classification_matrix(*, partition, threshold)`.

`tests/test_session_state.py` (78 inserciones, 0 borrados):
- 5 tests nuevos al final, antes del runner manual `__main__`.
- Reutilizan helpers existentes `_csv`, `_quiet_logger`, `_assert_raises`.
- Cero imports de pytest (estilo del archivo: `math.isclose` y helper
  custom para excepciones).

**Identidades verificadas a mano**:
- Fixture `_csv` (120 filas, `y = 1_{edad>=40}`): tras partition 70/30
  estratificado, test = 36 filas, 18 bads, 18 goods.
- Modelo CRT sobre ese fixture separa perfectamente: gains table OOS
  con `n_total=36`, `n_good=18`, `n_bad=18`, `n_excluded=0`,
  `KS = AUC = Gini = 1.0`.
- `threshold=0.3` en classification matrix: conteos TP+TN+FP+FN suman
  36.
- `partition="oot"` sin OOT cargado → `RuntimeError`.
- `partition="foo"` → `ValueError`.

**Hallazgos durante la implementación**:
- El asistente eligió extraer un helper privado (`_routed_partition`)
  aunque el prompt lo describía como opcional. Decisión correcta:
  evita duplicación y centraliza la validación de las tres particiones.
- Primer intento con prompt largo en prosa: Aider "conversó" en lugar
  de aplicar el edit. Segundo intento con prompt directo (empieza con
  "TAREA:... Aplica los cambios AHORA") + un solo archivo apuntado por
  invocación → aplicación inmediata. Lección operativa: incluir una
  orden explícita de edición al inicio del prompt, no solo la
  descripción del cambio.

**Tests**: 188/188 PASSED (183 previos + 5 nuevos).

**Referencias**: `docs/roadmap.md` (sección Fase 2.4),
`docs/estado_proyecto.md` (sección 3).

---

### 03/10/2026 — Fase 2.4.c.2.a: panel de reportes funcional

**Estado**: Aprobado tras 4 iteraciones de fix.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `frontend_v3/i18n.py`, `frontend_v3/reports_panel.py`
(commit final `58f2cd6`).

**Motivación**:
Segunda sub-fase de 2.4.c. Convertir el placeholder `ReportsPanel`
(una sola label centrada) en un panel funcional que consuma los DTOs
del backend (`Session.get_gains_table` / `Session.get_classification_matrix`)
y los renderice como tabla Qt y matriz de clasificación. Sin Export HTML
(eso es 2.4.c.2.c) ni cableado con MainWindow (2.4.c.2.b).

**Arquitectura del panel**:
- Señales Qt expuestas: `partition_changed(str)`, `view_changed(str, int)`,
  `threshold_changed(float)`, `refresh_requested()`.
- API pública: `set_session_available(*, train, oos, oot)`,
  `set_gains_table(dto)`, `set_classification_matrix(dto)`, getters
  `current_partition/view/threshold/n_buckets`, `refresh()`,
  `retranslate_ui()`.
- Layout: controles arriba (partición, vista, buckets, threshold,
  refresh), `QSplitter` vertical con tabla de gains (13 columnas) y
  bloque inferior con summary + matriz de clasificación 3×3.
- Sala limpia respetada: solo PySide6 + `frontend_v3.i18n`.
- 65 claves i18n nuevas (paridad EN/ES estricta).

**Cambios aplicados**:

`frontend_v3/i18n.py` (132 inserciones netas, 0 borrados).
`frontend_v3/reports_panel.py` (369 inserciones, 18 borrados).

**Incidentes y lecciones (crítico para futuras sesiones)**:

1. **El prompt de i18n fue escrito ANTES de tener el código final del
   panel.** Varios nombres de claves no coincidieron con los que el
   panel usa realmente, y faltaron claves dinámicas
   (`reports_partition_{code}`, `reports_matrix_{key}`). Iteraciones
   de fix: 4. **Regla adoptada**: cuando hay dependencia cruzada,
   primero se implementa el consumidor (panel), se extraen las claves
   de su uso real con un script (re sobre tr(...)), y **después** se
   actualiza i18n.

2. **Aider falló 3 veces seguidas sobre `frontend_v3/i18n.py`**:
   en lugar de aplicar la edición, el modelo "conversaba" sobre el
   estado del contexto. Patrón reproducible cuando el prompt incluye
   reemplazos estructurales sobre archivos con diccionarios largos.
   Los prompts con "TAREA: aplica ahora" mitigaron parcialmente.

3. **Excepción al flujo Aider (regla del 29/09)**: la última clave
   faltante (`reports_matrix_bad_capture_rate`) se añadió manualmente
   en VS Code. Motivo: tres intentos fallidos seguidos con el mismo
   archivo; seguir intentando quemaba tiempo sin mejorar la fiabilidad.

4. **Duplicación cosmética pendiente**: quedaron en `i18n.py` ~18 claves
   sin uso (`reports_col_good`, `reports_summary_*`, `reports_export_*`,
   `reports_no_gains`, `reports_no_matrix`, `reports_error_compute`) que
   se limpiarán en 2.4.c.2.c junto con la implementación del Export HTML.

**Identidades verificadas**:
- `set(_STRINGS["en"]) == set(_STRINGS["es"])`: paridad perfecta.
- Total claves: 198 EN / 198 ES (antes de la fase: 133).
- Suite: 188/188 PASSED.
- `ReportsPanel()` se instancia sin error en `MainWindow.__init__`.

**Tests**: 188/188 PASSED.

**Referencias**: `docs/roadmap.md` (sección Fase 2.4),
`docs/estado_proyecto.md` (sección 3).

---

### 03/10/2026 — Fase 2.4.c.2.b: cableado MainWindow ↔ ReportsPanel

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `frontend_v3/main_window.py` (commit `456a71c`),
`frontend_v3/reports_panel.py` (fix Qt6).

**Motivación**:
Tercera sub-fase de 2.4.c. Cablear el `ReportsPanel` recién funcional con
el ciclo de vida de `MainWindow` y con los DTOs que expone `Session`, sin
introducir lógica analítica en el frontend (sala limpia).

**Arquitectura del cableado**:
- 4 conexiones Qt en `_build_central`:
    partition_changed -> _on_reports_partition_changed
    view_changed      -> _on_reports_view_changed
    threshold_changed -> _on_reports_threshold_changed
    refresh_requested -> _refresh_reports_panel
- 3 triggers de refresco automático: `_on_wizard_finished`,
  `_on_evaluate_oos`, `_on_load_oot` invocan `_refresh_reports_panel`
  tras poblar el `MetricsPanel`.
- Limpieza en `_on_new_wizard`: `set_gains_table(None)` +
  `set_classification_matrix(None)` al resetear la sesión.
- `_refresh_session_indicator` propaga el estado de `Session` al panel
  vía `set_session_available(train=, oos=, oot=)`.
- Nuevo helper `_refresh_reports_panel` que consulta al backend y
  captura `RuntimeError`/`ValueError` (partición no disponible) para
  mostrar estado vacío en lugar de fallar.

**Cambios aplicados**:

`frontend_v3/main_window.py` (81 inserciones, 0 borrados).
`frontend_v3/reports_panel.py` (2 líneas: fix setTextAlignment en Qt6).

**Hallazgos**:

1. **Warnings Qt6 en `reports_panel.py`**: la versión inicial envolvía
   `Qt.AlignmentFlag.AlignRight | AlignVCenter` en `int(...)`. Qt6
   marcó `setTextAlignment(int)` como deprecado (960 warnings en una
   corrida de 4s). Fix: pasar el flag directamente sin cast. Cero
   warnings tras el fix.

2. **Comportamiento silencioso ante partición no disponible**: si el
   usuario selecciona una partición que el estado actual de `Session`
   no ofrece, `_refresh_reports_panel` captura la excepción y muestra
   estado vacío. Se registra WARNING en el log, sin diálogo.

**Identidades verificadas**:
- 188/188 tests sin warnings.
- `MainWindow` se construye y destruye sin error en EN y ES.
- El cableado no introduce imports nuevos de backend.

**Tests**: 188/188 PASSED (los E2E específicos del panel van en 2.4.c.2.c).

**Referencias**: `docs/roadmap.md` (sección Fase 2.4).

---

### 03/10/2026 — Fase 2.4.c.2.c.1 + 2.4.c.2.c.2: Export HTML y limpieza i18n

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `frontend_v3/reports_panel.py` (commit `450ff55`),
`frontend_v3/i18n.py` (commit `1eb4388`).

**Motivación**:
Cerrar las dos primeras piezas de 2.4.c.2.c: (a) exportar el panel de
reportes a HTML autocontenido, (b) limpiar las claves i18n huérfanas
acumuladas durante 2.4.c.2.a.

**2.4.c.2.c.1 — Export HTML** (`reports_panel.py`, 169 inserciones):

- Nuevo botón "Exportar HTML" en la fila de controles (objectName
  `reportsExport`), conectado a `_on_export_clicked`.
- `_build_report_html()` genera HTML autocontenido (CSS inline, sin
  assets externos) con: header + metadatos (partición, threshold) +
  tabla de gains + summary + matriz de clasificación + métricas
  derivadas (precision, recall, F1, bad capture rate).
- `_open_export_dialog(html)` abre un `QDialog` modal con
  `QTextBrowser` (preview) + botones "Guardar como..." y "Cerrar".
- `_save_html_to_file(parent, html)` usa `QFileDialog.getSaveFileName`
  con filtro `*.html` y nombre por defecto `treegov_report.html`;
  escribe con UTF-8 y notifica éxito/error vía `QMessageBox`.
- 11 claves i18n nuevas (EN/ES, paridad estricta).
- Sala limpia respetada: cero numpy/pandas/scipy/backend_v3.

**2.4.c.2.c.2 — Limpieza i18n** (`i18n.py`, 28 líneas eliminadas):

Se identificaron 14 claves sin uso (`reports_error_compute`,
`reports_export_copy_hint`, `reports_matrix_capture`,
`reports_matrix_real_bad/good`, `reports_no_gains`, `reports_no_matrix`,
`reports_summary_n/good/bad/bad_rate/ks/auc/gini`). Fueron residuos de
la fase 2.4.c.2.a, cuando el bloque i18n se escribió ANTES del código
del panel y algunos nombres no coincidieron con los que el panel usa
realmente.

Eliminación mediante script Python controlado (no edición manual),
verificando que cada clave aparecía exactamente 2 veces (EN + ES).

**Hallazgos y lecciones**:

1. **Detección de huérfanas con script**: un script con `re.findall` sobre
   `tr("...")` en `frontend_v3/`, `backend_v3/` y `tests/` identificó 35
   candidatas. De ellas, 17 eran **falsos positivos** (todas las
   `reports_col_*`, usadas vía `tr(key)` con `key in self._HEADER_KEYS`).
   Solo 14 eran huérfanas reales. Lección: el análisis estático no
   detecta uso dinámico de claves; hay que revisar manualmente la lista
   antes de borrar.

2. **Eliminación programática > edición manual**: para 28 líneas en un
   archivo grande, un script Python es más seguro y auditable que 28
   ediciones manuales. El script verifica el conteo esperado y aborta si
   algo no cuadra.

3. **Limpieza recurrente**: como el panel usa 4 patrones dinámicos
   (`tr('reports_sum_' + key)`, `tr('reports_matrix_' + key)`,
   `tr('reports_partition_' + code)`, y `tr(key)` sobre `_HEADER_KEYS`),
   futuras limpiezas de i18n deberán considerar esos patrones. Alternativa
   futura: reescribir el panel para enumerar claves explícitamente
   (`tr("reports_sum_n_total")` en lugar de componer con `+`), a cambio
   de más líneas. Decisión diferida.

**Identidades verificadas**:
- Paridad EN/ES tras la limpieza: 195 / 195.
- `set(_STRINGS["en"]) == set(_STRINGS["es"])`: perfecto.
- Suite: 188/188 PASSED sin warnings.

**Tests**: 188/188 PASSED (los E2E específicos del panel van en 2.4.c.2.c.3).

**Referencias**: `docs/roadmap.md` (sección Fase 2.4).

---

### 03/10/2026 — Fase 2.4.c.2.c.3 + cierre de 2.4.c.2

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `tests/test_reports_panel.py` (commit `75d1a5a`).

**Motivación**:
Cerrar 2.4.c.2 con los tests del `ReportsPanel` (7 tests unitarios,
archivo nuevo). Con esto la UI de reportes queda completa y verificada
para pasar a 2.4.d (tests E2E + cierre de Fase 2.4).

**Cambios aplicados**:

`tests/test_reports_panel.py` (nuevo, 215 líneas):
- 7 tests unitarios, estilo dual (pytest / python directo), siguiendo
  el patrón de `test_metrics_panel.py` (offscreen, `_get_app`,
  runner `__main__`).
- Cobertura:
  1. `test_panel_constructs` — instancia sin error.
  2. `test_retranslate` — EN ↔ ES sin excepción, verifica `_partition_label`.
  3. `test_set_session_available` — habilitación de opciones del combo.
  4. `test_set_gains_table_populates` — 13 columnas, `rowCount=1`, label "L0".
  5. `test_signals_emitted` — 3 señales (partition, view, threshold).
  6. `test_build_report_html_contains_data` — HTML con label y matrices.
  7. `test_export_empty_does_not_crash` — `QMessageBox` mockeado.

**Hallazgos durante la implementación**:

1. **`test_signals_emitted` falló en primer intento**: el combo de
   partición arranca en "oos" (default del panel), y
   `setCurrentIndex("oos")` no dispara `currentIndexChanged` si el
   índice no cambia. Fix: forzar primero el estado a "train"/"leaf"
   antes de conectar las señales y luego moverse a "oos"/"bucket".
   **Lección operativa**: cuando se testean señales de Qt, verificar
   que el cambio de estado sea *efectivo* (índice distinto al actual).

2. **`test_build_report_html_contains_data` falló en primer intento**:
   el test asumía que el HTML contenía las cadenas literales "TP" y
   "TN", pero `_build_report_html` usa las claves i18n
   `reports_matrix_pred_good/bad` y `reports_matrix_actual_good/bad`
   para las cabeceras de la matriz (no incluye literales "TP"/"TN").
   Fix: verificar `tr("reports_matrix_pred_good")` y
   `tr("reports_matrix_pred_bad")` en su lugar.
   **Lección operativa**: al escribir tests de HTML generado, verificar
   los identificadores reales del generador, no supuestos del revisor.

**Cierre de 2.4.c.2**:
Los 3 sub-pasos (a: panel + i18n, b: cableado MainWindow, c: Export HTML
+ limpieza i18n + tests) están completos. La UI de reportes está
operativa end-to-end: el usuario entrena, evalúa OOS/OOT, y la pestaña
"Reports" muestra tabla de gains + matriz, con export HTML funcional.

**Identidades verificadas**:
- Suite: 195/195 PASSED (188 previos + 7 nuevos).
- `test_reports_panel.py` pasa con pytest y con python directo.
- Sin warnings en toda la suite.

**Tests**: 195/195 PASSED.

**Referencias**: `docs/roadmap.md` (sección Fase 2.4),
`docs/estado_proyecto.md` (sección 3).

---

### 03/10/2026 — Fase 2.4.d: tests E2E + cierre de Fase 2.4

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `tests/test_e2e_reports.py` (commit `d838512`).

**Motivación**:
Último sub-paso de Fase 2.4. Cubrir el flujo end-to-end del panel de
reportes: carga de CSV → entrenamiento → tabla de gains poblada →
cambio de partición → export HTML → escritura a disco.

**Cambios aplicados**:

`tests/test_e2e_reports.py` (nuevo, 205 líneas):
- 4 tests E2E, estilo dual (pytest / python directo), con helpers
  reutilizados de `test_e2e_mainwindow.py`.
- Cobertura: populate tras train, cambio de partición, click export
  build HTML, save-as escribe archivo.

**Hallazgos**:

1. **Prompts endurecidos**: antes de escribir el prompt, se
   identificaron 2 riesgos de fallo (asumir combo "train" habilitado
   tras entrenar; asumir tabla poblada con el fixture). Se añadieron
   pre-asserts explícitos. Los 4 tests pasaron a la primera.

2. **Sin warnings**: la corrección `setTextAlignment` (2.4.c.2.b) sigue
   vigente; la corrida completa es limpia.

**Cierre de Fase 2.4**:
Los 4 sub-pasos (a, b, c, d) están completos. El usuario puede: cargar
datos, entrenar, evaluar OOS/OOT, y en la pestaña "Reports" ver la
gains table + matriz de clasificación para cualquier partición
disponible, con export HTML autocontenido.

**Identidades verificadas**:
- Suite: 199/199 PASSED (195 previos + 4 nuevos).
- `test_e2e_reports.py` pasa con pytest y con python directo.

**Tests**: 199/199 PASSED.

**Referencias**: `docs/roadmap.md`, `docs/estado_proyecto.md`.

---

### 03/10/2026 — Publicación 1.0.0a1 en PyPI

**Estado**: Aprobado.
**Modelo**: N/A (publicación manual con twine 7.0.0).
**Revisor**: Marco Rengel
**Artefactos**: `pyproject.toml`, `frontend_v3/__init__.py`, `README.md`,
`README.es.md` (commit `9273395`).

**Motivación**:
Cierre de Fase 2 del roadmap. El nombre `treegov` ya estaba reservado en
PyPI con un placeholder (`1.0.0a0`, 3.6 kB). Esta publicación reemplaza
ese placeholder por el paquete real con `backend_v3` + `frontend_v3`.

**Cambios aplicados**:

- `pyproject.toml`: versión `1.0.0a0` → `1.0.0a1`; packages
  `["backend_v3"]` → `["backend_v3", "frontend_v3"]`; añadido
  `[tool.setuptools.package-data]` con `frontend_v3 =
  ["resources/*.qss"]` (sin esto la GUI crashea al no encontrar el QSS).
- `frontend_v3/__init__.py`: `__version__` bump a `1.0.0a1`.
- `README.md` / `README.es.md`: links relativos → absolutos
  (`https://github.com/...`) para que rendericen en PyPI; conteo de
  tests actualizado a 199.

**Proceso**:

1. Token PyPI regenerado con scope de proyecto (`treegov-upload-2026`).
2. Guardado en `~/.pypirc` vía `Read-Host -AsSecureString` (sin
   exposición en terminal ni en prompts de Aider).
3. `pyproject-build` → `treegov-1.0.0a1-py3-none-any.whl` (114 kB)
   + `treegov-1.0.0a1.tar.gz` (155 kB).
4. `twine check dist/*` → PASSED en ambos.
5. Verificado que `styles.qss` y los 25 módulos `.py` están en el wheel.
6. `twine upload dist/*` → exitoso. HTTP 200 confirmado vía
   `curl https://pypi.org/pypi/treegov/1.0.0a1/json`.
7. **Prueba de instalación limpia**: `python -m venv` en `C:\temp\`,
   `pip install treegov==1.0.0a1`, import de `backend_v3` y `frontend_v3`
   exitoso. Confirma que el paquete es instalable desde PyPI en cualquier
   máquina.

**Lecciones**:

- **Nunca pegar código de PowerShell con bloques multilínea desde el
  chat**: en la primera iteración, el portapapeles reemplazó el token
  por el texto del comando. Solución: usar `Read-Host -AsSecureString`
  en un solo bloque de 3-4 líneas.
- **`package-data` explícito para recursos no-Python**: aunque
  `frontend_v3` estuviera en `packages`, el `.qss` requiere
  declaración explícita en `[tool.setuptools.package-data]`.
- **`twine check` antes del upload**: detecta errores de README y
  metadata que PyPI rechazaría.

**Identidades verificadas**:

- `https://pypi.org/project/treegov/1.0.0a1/` → página accesible.
- `curl .../json` → HTTP 200.
- Contenido del wheel: `frontend_v3/resources/styles.qss` presente.
- Instalación limpia desde PyPI: `backend_v3 OK` + `frontend_v3 OK`.

**Tests**: 199/199 PASSED (sin cambios en código).

**Referencias**: `docs/roadmap.md`, `docs/estado_proyecto.md`.

---

### 04/10/2026 — Fase 3.0: cierre de la "zona gris" documental

**Estado**: Aprobado.
**Modelo**: N/A (auditoría documental + redacción manual).
**Revisor**: Marco Rengel
**Artefactos**: `docs/design_decisions.md` (nuevo, 47.784 bytes),
`docs/methodology.md` (16 subsecciones nuevas),
`docs/roadmap.md` (redistribución de fases 3-7),
`docs/estado_proyecto.md` (referencias),
`docs/api.md` (cross-reference).

**Motivación**:
Durante las sesiones previas se identificó una "zona gris": decisiones
de implementación tomadas en Fases 0-2 que **no están documentadas en
`methodology.md` ni en `audit_log.md`**. El código sí está bien
documentado internamente (docstrings excelentes), pero un auditor que
solo lee los documentos formales **no puede reconstruir el modelo real**
sin abrir el código.

Esta fase cierra esa zona gris antes de empezar la analítica avanzada
(3.1 a 3.6), para que las decisiones futuras se tomen sobre una base
documental sólida.

**Inventario de decisiones implícitas detectadas**:

Se auditaron los 14 módulos de `backend_v3/` y se identificaron 38
decisiones no documentadas formalmente. Clasificación:

| Categoría | Descripción | Nº |
|---|---|---|
| **A** | Trazabilidad pura (no alteran la matemática) | ~15 |
| **B** | Alteran la matemática pero son elección explícita del usuario (BANKING/RESEARCH, parámetros con default) | ~10 |
| **C** | Desviaciones respecto a la literatura canónica, documentadas pero potencialmente invisibles al usuario | 4 |
| **D** | Decisión de política de API, no matemática | 9 |

De las 38, **4 están en la categoría "C"** (canónico vs TreeGov) y se
planifican como parámetros configurables en la sub-fase 3.0.g.

**Cambios aplicados**:

**1) `docs/design_decisions.md` (nuevo, 47.784 bytes)**:
- Documento dedicado a decisiones de *implementación* (distinto de
  `methodology.md`, que es matemática pura).
- Estructura: §0 (dominio y perfiles de usuario) + §1 a §10
  (decisiones por módulo/área) + §11 (parámetros a exponer).
- Formato por decisión: Contexto / Alternativas / Elección /
  Justificación / Consecuencias / Referencias cruzadas.
- Incluye un análisis honesto de cobertura por perfil de usuario
  (econometrista de crédito / biólogo o científico social) con gaps
  explícitos.

**2) `docs/methodology.md` (16 subsecciones nuevas)**:
- Añadidas como subsecciones al final de cada sección existente, sin
  renumerar ni reorganizar:
  - §1.7 Cochran contado en c→r
  - §1.8 p-valor del par en subtabla 2×K
  - §1.9 Exhaustive CHAID incluye paso 0
  - §2.7 `min_child_size` como piso absoluto
  - §2.8 Cuadrantes de surrogates (identidad)
  - §2.9 Agreement > majority_to_beat
  - §3.3 Bonferroni `M=2J` (TreeGov) vs `J` (canónico)
  - §3.4 Nominal K>10 por tasa (vs dummies+LDA)
  - §3.5 Raíz QDA restringida al intervalo inter-medias
  - §3.6 Priors empíricos en QDA
  - §6.5 Modo RESEARCH sin floor
  - §7.1 Poda coste-complejidad (Breiman)
  - §8.7 PSI clip ε sin renormalizar
  - §8.8 CSI deciles aprendidos en train
  - §8.9 HL π_g clip a [1e-15, 1-1e-15]
  - §8.10 PR-AUC step-wise
- Cada subsección tiene 5-15 líneas con: fórmula, convención TreeGov,
  diferencia con literatura, referencia cruzada a `design_decisions.md`.

**3) `docs/roadmap.md` (redistribución de fases 3-7)**:
- El roadmap original agrupaba en "Fase 3" tres familias distintas:
  analítica avanzada + reportes/export + capa MCP.
- Redistribución aprobada el 04/10/2026:
  - **Fase 3**: analítica avanzada + documentación + validación
    (3.0 doc, 3.1 multiclase, 3.2 ponderación, 3.3 Indet/No Perf,
    3.4 CRT/QUEST multiclase, 3.5 reportes, 3.6 validación con datos
    públicos, 3.6.b modo no-bancario, 3.7 v1.0.0).
  - **Fase 4**: reportes avanzados + export (SQL, Python, reglas
    MD/JSON, doc automática).
  - **Fase 5**: capa MCP.
  - **Fase 6**: batch scoring + champion-challenger.
  - **Fase 7**: IFRS 9 / ECL.
- Añadido un `## Documentation map` al final del roadmap listando
  los 9 documentos con su propósito y audiencia.

**4) `docs/estado_proyecto.md`**:
- Actualizada la sección 3 ("Fases pendientes") con la redistribución.
- Añadido `design_decisions.md` a la estructura de directorios.
- Añadido `design_decisions.md` a la lista de lectura del apartado
  "Cómo reconstruir el contexto en una nueva sesión".

**5) `docs/api.md`**:
- Añadida sección "Cross-reference — design decisions" al final,
  con punteros a las decisiones relevantes para usuarios de la API.

**Hallazgos y lecciones**:

1. **El código está mejor documentado que los documentos formales.**
   Los 14 módulos de `backend_v3/` tienen docstrings excelentes que
   explican el "por qué" de cada decisión. Pero un auditor MRM no lee
   código: lee documentos. `design_decisions.md` puentea ese gap.

2. **Cuatro desviaciones canónicas identificadas** (QUEST Bonferroni
   `M=2J`, QUEST nominal K>10 por tasa, QUEST raíz QDA restringida,
   PSI sin renormalizar). Todas ya estaban documentadas en el código,
   pero no en `methodology.md`. Ahora sí, con referencia cruzada a
   `design_decisions.md`.

3. **Análisis honesto de cobertura por perfil de usuario.** El nuevo
   `design_decisions.md` §0 documenta explícitamente qué cubre TreeGov
   hoy y qué no, para un econometrista de crédito y para un biólogo.
   Esto es coherente con la política MRM del proyecto: nada oculto.

4. **Redistribución de fases necesaria.** La "Fase 3" original
   mezclaba tres familias de trabajo con dependencias distintas.
   Separarlas en fases independientes mejora el foco y permite
   trackear progreso con claridad.

**Identidades verificadas**:
- `design_decisions.md` creado con 12 secciones (§0 a §11) +
  `## Maintenance`.
- 44 subsecciones (`### X.Y`) en total.
- `methodology.md` contiene las 16 subsecciones nuevas en las
  posiciones correctas (verificado con `Select-String`).
- `roadmap.md` tiene las 5 fases renumeradas + `## Documentation map`.
- `estado_proyecto.md` referencia `design_decisions.md` en 3 sitios.
- `api.md` contiene `## Cross-reference — design decisions`.

**Tests**: 199/199 PASSED (sin cambios en código).

**Referencias**:
- `docs/design_decisions.md` (nuevo documento).
- `docs/methodology.md` §1.7 a §8.10 (16 subsecciones nuevas).
- `docs/roadmap.md` (redistribución de fases).

---

### 04/10/2026 — Fase 3.0.g: parámetros canónicos vs TreeGov

**Estado**: Aprobado.
**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**: `backend_v3/quest_engine.py` (commit `4c7e55d`),
`backend_v3/stability.py` (commit `62753b7`),
`tests/test_quest_engine.py`, `tests/test_stability.py`.

**Motivación**:
Cerrar la exposición de las 4 decisiones de "Categoría C" identificadas
en la auditoría 3.0 (§11 de `design_decisions.md`): desviaciones
deliberadas de TreeGov respecto a la literatura canónica. Exponerlas
como parámetros permite al usuario elegir el comportamiento canónico
sin perder el default actual.

**Los 4 parámetros expuestos**:

1. **`bonferroni_family: int = 2`** (QUEST) — Multiplicador de la
   familia de tests en la corrección de Bonferroni. TreeGov usa 2
   (medias + varianzas); Loh & Shih canónico usa 1. Con `= 1`, el
   umbral es `α/J` y `m = J` (canónico).
2. **`nominal_high_card: str = "rate"`** (QUEST) — Estrategia para
   nominales K>10. TreeGov usa `"rate"` (Breiman); canónico es
   `"dummies_lda"` (Loh & Shih), reservado para Fase 3.4 (lanza
   `NotImplementedError` si se pide).
3. **`qda_root_restriction: bool = True`** (QUEST) — Restricción de
   la raíz QDA al rango inter-medias. TreeGov `True`; canónico `False`
   (acepta cualquier raíz real, con desempate por cercanía a la media
   ponderada).
4. **`renormalize: bool = False`** (StabilityMonitor/psi_index) —
   Renormalización tras el clip ε en PSI/CSI. TreeGov `False`
   (preserva señal de bins vacíos); canónico `True`.

**Cambios aplicados**:

**`backend_v3/quest_engine.py`** (113 inserciones, 18 borrados):
- `__init__` ampliado con los 3 parámetros keyword-only, validaciones
  y guardado como atributos públicos.
- `nominal_high_card="dummies_lda"` → `NotImplementedError` inmediato.
- `umbral` y `_mk_selection` usan `self.bonferroni_family` en lugar de
  `2` hardcodeado.
- Guard de defensa en profundidad en `_subset_cut`.
- Bifurcación en `_qda_cutpoint` (restringida vs canónica).
- Docstrings de clase e `__init__` en inglés.

**`backend_v3/stability.py`** (45 inserciones, 6 borrados):
- `psi_index` gana parámetro keyword-only `renormalize: bool = False`.
- `StabilityMonitor.__init__` gana el mismo parámetro.
- Las 2 llamadas internas propagan `renormalize=self.renormalize`.

**`tests/test_quest_engine.py`** (60 inserciones):
- 4 tests nuevos: bonferroni canónico, bonferroni inválido, QDA
  canónico (raíz más cercana a x̄), nominal_high_card no implementado.

**`tests/test_stability.py`** (38 inserciones):
- 3 tests nuevos: renormalize cambia el resultado con bins vacíos,
  renormalize es no-op con distribuciones ya normalizadas, validación
  de tipo.

**Identidades verificadas**:

- Con defaults (`bonferroni_family=2`, `nominal_high_card="rate"`,
  `qda_root_restriction=True`, `renormalize=False`): **cero cambio
  numérico**. Los 199 tests previos siguen verdes sin modificar sus
  valores esperados.
- `bonferroni_family=1`: `m = J` (canónico). Test lo verifica con
  fixture de 3 predictores: `m = 3`, no 6.
- `qda_root_restriction=False`: acepta raíces fuera del rango
  inter-medias. Test con fixture de dos raíces reales (1.6915 y
  -1.7582, ambas fuera de [0, 0.5]): el modo canónico devuelve
  1.6915 (la más cercana a x̄=0.25). El modo restringido (default)
  devuelve el fallback 0.25.
- `nominal_high_card="dummies_lda"`: `NotImplementedError` con
  mensaje que apunta a Fase 3.4.
- `renormalize=True` con bins vacíos: valor distinto al default.
- `renormalize=True` con distribuciones ya normalizadas: idéntico al
  default (no-op).

**Incidentes durante la implementación**:

1. **Error del revisor (typo)**: el prompt inicial usó
   `math.isclose(..., abs=1e-3)` en lugar de `abs_tol=1e-3`.
   Corregido manualmente en VS Code.
2. **Error del revisor (cálculo)**: asumí que el modo QDA canónico
   devolvería la raíz -1.7582 (más lejana a x̄=0.25), cuando el
   criterio es "más cercana a x̄" — la raíz correcta es 1.6915. El
   motor tenía razón; corregido el test.

**Tests**: 206/206 PASSED (199 previos + 4 nuevos QUEST + 3 nuevos
stability).

**Referencias**:
- `docs/design_decisions.md` §11 (tabla de los 4 parámetros).
- `docs/design_decisions.md` §4.1, §4.2, §4.3, §7.4.

---

### 04/10/2026 — Fase 3.1.a: diseño estructural multiclase

**Estado**: Aprobado. Pendiente de implementación.
**Modelo**: N/A (autoría manual por el asistente estratégico).
**Revisor**: Marco Rengel
**Artefactos**: `docs/3.1_design_multiclass.md` (nuevo, ~40 KB,
~1000 líneas, 13 secciones).

**Motivación**:
Antes de empezar la implementación de multiclase (Fase 3.1), se
redactó el diseño estructural completo. Motivo: multiclase toca la
capa más profunda del modelo (`TreeNode`, `TreeModel`, `TreeBuilder`)
y cada consumidor binario (`validation`, `reporting`, `stability`,
GUI) debe ser verificado. Un diseño auditado antes del código
previene refactorizaciones y zonas grises.

**Decisiones clave del diseño**:

1. **`TreeNode.pd_final` y `pd_jeffreys` pasan a `tuple[float, ...]`.**
   `n_events` pasa a `tuple[int, ...]`. Único tipo, invariante
   `sum == 1` verificable.

2. **Nuevo campo `TreeNode.class_labels: tuple[str, ...]`.**
   Trazabilidad: cualquier consumidor que lea `pd_final[c]` puede leer
   `class_labels[c]` para saber qué clase representa.

3. **`TreeModel` gana `class_labels`, `target_class`,
   `target_class_index`.**
   Fingerprint los refleja.

4. **Jeffreys multivariante:**
   `pd_jeffreys[c] = (k_c + 0.5) / (n + K * 0.5)`.
   Reducción exacta al binario para K=2. Prior: media posterior de
   `Dirichlet(0.5, ..., 0.5)`. Cita: Jeffreys (1946).

5. **`pd_floor` en multiclase:** se aplica componente a componente y
   se renormaliza. Preserva el invariante `sum == 1`. Soft floor en
   lugar de floor estricto por componente.

6. **§1bis — `target_class` y `class_labels` OBLIGATORIOS.**
   Sin defaults. `Session.fix_spec` los exige. `TypeError` si se
   omiten. `ValueError` si el valor no está en las clases observadas.

   **Motivo:** evitar el problema clásico de "clase de interés
   invertida" que en SPSS/R/sklearn se resuelve con `pos_label=1` y
   que muchos analistas olvidan. Resultado del olvido: métricas
   invertidas silenciosamente (Gini negativo, cum decreciente,
   recall bajo). Cero defaults para forzar la decisión.

7. **§1ter — Validaciones pre-entrenamiento (wizard):**
   - **Check A:** combo solo ofrece clases observadas (no texto libre).
   - **Check B:** cada opción muestra el conteo de su clase.
   - **Check C:** warning amarillo visible si se elige la clase
     mayoritaria. No bloqueante pero registrado en log.
   - Los 3 checks son complementarios, activos a la vez.

8. **§1quater — Alertas post-entrenamiento:**
   - **Gini negativo** → badge rojo con mensaje "verifique si
     `target_class` está invertido".
   - **`event_rate_cum` decreciente** en gains table → mismo badge.
   - **Botón de reversión** con un clic: invierte la clase, reusa
     todos los parámetros, reentrena.

9. **Reordenamiento canónico interno:** la clase de interés siempre
   ocupa el índice 0 del vector PD. Consumidores leen `pd_final[0]`
   para la clase de interés, independientemente del valor numérico
   original en los datos.

10. **CHAID es el único motor multiclase en 3.1.** C&RT y QUEST
    bloquean K > 2 con mensaje que apunta a Fase 3.4.

11. **Métricas y reportes siguen bloqueando K > 2 en 3.1.** Se abren
    en Fase 3.5. Bloqueo con mensaje claro que apunta a la fase
    futura.

12. **`predict_pd` pasa a devolver `np.ndarray` 2D** `(n_rows, K)`.
    Consumidores binarios leen `pd_2d[:, 0]`.

13. **Fingerprint incluye `target_class`, `class_labels`, `n_classes`.**
    Dos árboles con distinta clase de interés nunca comparten
    fingerprint. Esto invalida fingerprints previos a 3.1
    (documentado; alpha sin producción).

**Sub-fases de implementación** (6 sesiones estimadas):

| Sub-fase | Alcance |
|---|---|
| 3.1.a | `TreeNode`/`TreeModel` tuple fields + `TreeBuilder.target_class` |
| 3.1.b | Jeffreys multivariante + floor renormalizado + reordenamiento |
| 3.1.c | `Session.fix_spec` + `SessionState` + bloqueo C&RT/QUEST |
| 3.1.d | `predict_pd` 2D + bloqueos en validation/reporting/stability |
| 3.1.e | Wizard: selección obligatoria + counts + warning minoritaria |
| 3.1.f | MetricsPanel: badge Gini negativo + botón de reversión |

**Tests planificados:**

- ~25-30 tests nuevos.
- ~30-40 tests adaptados (escalar → tuple).
- 0 tests retirados.

**Invariante no negociable:**
Para K=2 con `target_class=1` y labels estándar, el modelo producido
es **numéricamente idéntico** al pre-3.1. Verificado por
`test_multiclass_binary_parity`.

**Tests**: 206/206 PASSED (sin cambios en código; solo documento nuevo).

**Referencias**:
- `docs/3.1_design_multiclass.md` (documento nuevo).
- `docs/design_decisions.md` §5.2, §6.4, §0.4.

---

### 04/10/2026 — Fase 3.1.a: multiclase en árbol — implementación completa

**Estado**: ✅ CERRADA. Código y tests adaptados. Suite en 210/210.

**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2).
**Revisor**: Marco Rengel
**Artefactos**:
- `backend_v3/tree_builder.py` — adaptado (tuple + class_labels + target_class)
- `backend_v3/pruning.py` — adaptado
- `backend_v3/reporting.py` — adaptado
- `backend_v3/validation.py` — adaptado
- `backend_v3/session_state.py` — adaptado (target_class temporal)
- `frontend_v3/tree_view.py` — adaptado
- `tests/test_tree_builder.py` — adaptado (16/16 passed)

**Motivación**:
Primera implementación de multiclase. Se aplicó el diseño
`docs/3.1_design_multiclass.md` §1 a §3 y §7 (parte de código, sin
tocar SessionState ni Session.fix_spec todavía — eso va en 3.1.c).

**Cambios aplicados**:

`tree_builder.py` (178 inserciones, 55 borrados):
- TreeNode: n_events/pd_jeffreys/pd_final pasan a tuple[..., K];
  nuevo campo class_labels.
- TreeModel: nuevos campos class_labels / target_class /
  target_class_index; 3 invariantes nuevos (longitudes coherentes,
  sum(pd_final)==1, n_events[c] <= n por clase).
- TreeBuilder.__init__: nuevo parámetro obligatorio target_class.
- TreeBuilder.build: reordenamiento canónico (target_class en índice 0),
  Jeffreys multivariante, floor renormalizado.
- TreeBuilder._fingerprint: firma ampliada + 4 entradas nuevas.

`pruning.py` (13 inserciones, 8 borrados):
- r(t) generalizado a `n - max(n_events)` (idéntico a `min(k, n-k)`
  para K=2).
- _rebuild propaga class_labels / target_class / target_class_index.

`reporting.py` (15 inserciones, 1 borrado):
- Check binario: K != 2 → ValueError (delegando la matriz a Session).
- Lectura de pd_final[0].

`validation.py` (4 inserciones, 1 borrado):
- predict_pd: lectura de pd_final[0].

`session_state.py` (17 inserciones, 5 borrados):
- Atributo temporal `self._target_class = 1` (hasta 3.1.c).
- Session.train gana `target_class` (parámetro temporal).
- TreeBuilder(target_class=...) en train.
- 4 lecturas de pd_final → pd_final[0].

`tree_view.py` (11 inserciones, 6 borrados):
- 6 lecturas de pd_final / pd_jeffreys / n_events → [0].
- Docstring del módulo actualizado.

`test_tree_builder.py` (adaptado completo, 16/16 passed):
- Reemplazo global de `target_type=_BIN,` → añade `target_class=1`.
- Adaptaciones específicas de tests con fixtures manuales de TreeNode.

**Estado de la suite**:
- Antes de empezar 3.1.a: 206/206.
- Tras la implementación de `tree_builder.py` (sesión 1): 42 fallos
  esperados (TreeNode/TreeBuilder firmas cambiadas).
- Tras adaptar los 5 consumidores + `test_tree_builder.py`:
  **180 passed / 26 failed**.
- Los 26 fallos son todos mecánicos (mismo patrón que ya se resolvió
  en `test_tree_builder.py`) y se concentran en:
  - `test_pruning.py` (6)
  - `test_reporting.py` (9)
  - `test_stability.py` (1)
  - `test_tree_view.py` (9)
  - `test_validation.py` (1)

**Cierre de 3.1.a**:
- Los 5 archivos de tests pendientes adaptados.
- Añadidos 4 tests nuevos en `test_tree_builder.py`:
  - `test_multiclass_binary_pd_values` — PDs exactas K=2 (mismo
    resultado que el pre-3.1).
  - `test_multiclass_binary_pd_sums_to_one` — invariante suma=1.
  - `test_multiclass_target_class_inverted` — invertir target_class
    invierte las PDs.
  - `test_multiclass_k3_builds` — K=3 con CHAID construye.
- Suite: 210/210 PASSED.

**Lección operativa (importante para el próximo chat)**:
Cuando una firma cambia en código que produce muchos fallos en tests,
el patrón "reemplazo global + casos especiales" es más efectivo que
pedir a Aider que aplique 30 cambios en un archivo de tests. Aider
rinde bien para cambios quirúrgicos; para bulk de tests, VS Code
con Ctrl+H es más rápido y seguro.

**Referencias**:
- `docs/3.1_design_multiclass.md` (§1-§3, §7).
- `docs/design_decisions.md` §5.2, §6.4.

---

### 04/10/2026 — Fase 3.1.c: pasos 1-3 cerrados; paso 4 revertido y reprogramado

**Estado**: Parcial. Pasos 1, 2 y 3 cerrados. Paso 4 (endurecimiento de
firmas) intentado, revertido y reprogramado para próxima sesión. Paso 5
(documentación) pendiente.

**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2, whole edit
format).

**Revisor**: Marco Rengel

**Artefactos (commits)**:

- `27d9e5b` — Paso 1: `TreeBuilder.__init__` acepta `class_labels`
  opcional (default temporal `None`). 40 inserciones, 1 borrado.
- `7b746be` — Paso 2b: `test_guards_target` adaptado a multiclase
  (eliminado el bloque y3). 7 borrados.
- `574c800` — Paso 2: `SessionState` gana `target_class` y
  `class_labels`; `fix_spec` y `train` propagan; bloqueo multiclase
  C&RT/QUEST. 102 inserciones, 11 borrados.
- `c3b37e6` — Paso 3: adaptación mecánica de ~19 llamadas a
  `fix_spec`; 11 tests nuevos de 3.1.c (obligatoriedad, persistencia,
  multiclase K=3, bloqueo CRT/QUEST, CHAID y CHAID_EXHAUSTIVE
  permitidos, `class_labels_dict`). 189 inserciones, 26 borrados.

**Motivación**:

Diseño de 3.1.c en `docs/3.1_design_multiclass.md` §4. Plan aprobado
en 5 pasos (a, b, c, d, e) más un paso 5 documental.

**Decisiones clave aplicadas**:

- `fix_spec` gana `target_class` y `class_labels` con default temporal
  `None` (paso 2). La lógica de validación se implementa completa ya
  (cobertura exacta, `{0,1}` binario estricto, K≥3 libre); los defaults
  solo cubren inputs de tests antiguos, no relajan validaciones.
- `SessionState` gana `target_class: int | str | None = None` y
  `class_labels: tuple[tuple[int | str, str], ...] = ()`.
- `Session.train` lee `st.target_class` y `st.class_labels` como fuente
  de verdad; calcula `class_labels_canonical` (target_class en índice 0,
  resto ascendente); los pasa a `TreeBuilder`.
- Bloqueo multiclase: `Session.train` con K>2 solo admite CHAID y
  CHAID_EXHAUSTIVE; C&RT y QUEST lanzan `ValueError` con mensaje que
  apunta a Fase 3.4. El bloqueo ocurre antes de instanciar el engine
  (atomicidad).
- Property nueva `Session.class_labels_dict`.

**Incidentes durante la implementación**:

1. `test_guards_target` falló tras el Paso 2 por la razón correcta:
   el bloque y3 del test asumía que `fix_spec("y3")` con 3 clases
   lanzaba `ValueError`, pero ya no. Adaptado en el sub-paso 2b.
2. La fixture `_csv_k3` (introducida en el prompt del Paso 3) usaba
   `edad` como predictor continuo, y CHAID rechaza continuos. Los tests
   `test_train_allows_chaid_multiclass` y
   `test_train_allows_chaid_exhaustive_multiclass` fallaron. Corregido
   en un prompt correctivo: la fixture ahora usa solo predictores
   categóricos (`seg1`, `seg2`). Lección: cuando se diseña una fixture
   para CHAID, verificar que los predictores son categóricos.
3. El Paso 4 (endurecimiento: `class_labels` y `target_class` sin
   default en `TreeBuilder` y `fix_spec`; eliminar `target_class` de
   `Session.train`) se intentó con un único prompt multi-archivo y
   resultó en 46 tests fallidos. La causa no es un bug del edit, sino
   que el endurecimiento de firmas rompe llamadas en:
   - `frontend_v3/main_window.py` (`_train_pipeline` llama `fix_spec`
     sin los nuevos kwargs).
   - `tests/test_pruning.py`, `tests/test_stability.py`,
     `tests/test_tree_builder.py`, `tests/test_tree_view.py`,
     `tests/test_validation.py`, `tests/test_wizard.py`,
     `tests/test_e2e_mainwindow.py`, `tests/test_e2e_reports.py`
     (construyen `TreeBuilder` sin `class_labels`, o llaman `fix_spec`
     sin los kwargs).
   El Paso 4 fue revertido con `git checkout --` sobre los 3 archivos
   modificados. Suite en 221/221 de vuelta.

**Estado del Paso 4**: reprogramado. Requiere plan de mayor alcance:

- **4.1** — Adaptar el frontend (producción):
  `frontend_v3/wizard.py` (construcción del `cfg`) y
  `frontend_v3/main_window.py` (`_train_pipeline`).
- **4.2** — Adaptación mecánica de los ~7 archivos de tests.
- **4.3** — Verificación.

Requiere inspeccionar `frontend_v3/wizard.py` y el fragmento relevante
de `frontend_v3/main_window.py` antes de escribir prompts.

**Tests**: 221/221 PASSED en el commit `c3b37e6` (Paso 3 cerrado).
Tras el intento fallido del Paso 4: 175/221 (revertido a 221/221).

**Referencias**:

- `docs/3.1_design_multiclass.md` §1bis, §2, §4, §7.
- `docs/design_decisions.md` §0.3, §5.2, §5.3.

**Pendientes de 3.1.c**:

- Paso 4 (endurecimiento) — reprogramado.
- Paso 5 (documentación: reconciliar `3.1_design_multiclass.md` §4.1
  con K=2 `{0,1}` estricto vs K≥3 libre; aclarar
  `CHAID_EXHAUSTIVE` permitido con K>2; añadir entrada nueva en
  `design_decisions.md` sobre `class_labels` como obligatorio en
  `TreeBuilder` y `fix_spec`; entrada de cierre en audit_log).

---

### 09/10/2026 — Migración de Aider a OpenCode; hallazgo de caché y saldo

**Estado**: Aprobado. Herramienta activa: OpenCode 1.18.35.

**Motivación**:
Durante las sesiones del 05-07/10 se consumieron $26.82 en 4 días con
Aider 0.86.2 + Kimi K3. El análisis del Product Bill reveló: $25.97 en
Model Inference, $0.05 en Context Caching. Es decir, la caché no estaba
funcionando: Aider no envía los "cache control breakpoints" que
Moonshot/Kimi requiere para cachear de forma efectiva.

**Hallazgo técnico**:

- Aider 0.86.2 solo soporta caché explícita para Anthropic y DeepSeek.
  Para Kimi K3, el mecanismo prompt_cache_options configurado en
  ~/.aider.model.settings.yml no llega correctamente a la API.
- Un timeout de 15 minutos (07/10) consumió $0.80 sin producir diff.
- OpenCode 1.18.35 tiene soporte nativo para providers OpenAI-compatible
  y configuración de caché vía setCacheKey.

**Artefactos**:

- OpenCode actualizado de 1.18.32 a 1.18.35 (npm).
- Autenticación: opencode auth login -> Moonshot AI (internacional) ->
  key guardada en ~/.local/share/opencode/auth.json.
- .aider.conf.yml: map-tokens: 1024, cache-prompts: true,
  caches_by_default: true.
- ~/.aider.model.settings.yml: cache_control: true,
  prompt_cache_options (no efectivo).
- Aider queda como respaldo documentado (Opción Y). No se desinstala.

**Pendientes de 3.1.c**:

- A.1: entrada del Paso 4 en audit_log.md (este bloque es la entrada de
  hoy, no la del Paso 4).
- A.2: reconciliar docs/3.1_design_multiclass.md sección 4.1.
- A.3: reconciliar docs/design_decisions.md secciones 5.2, 5.3 + nueva
  entrada sobre class_labels.
- Paso 5: cierre documental completo.

**Referencias**: docs/prompt_para_asistente.md sección 6,
docs/contexto_para_nueva_sesion.md.

---

### 09/10/2026 — Configuración de OpenCode y decisión de herramienta activa

**Estado**: Aprobado. OpenCode 1.18.35 pasa a ser la herramienta
activa de desarrollo. Aider 0.86.2 queda como respaldo documentado.

**Motivación**:
Tras la migración de Aider a OpenCode documentada en la entrada
anterior, se configura OpenCode para el proyecto TreeGov con el
objetivo de reducir el consumo de tokens en Kimi K3 y establecer
un flujo de trabajo más eficiente.

**Configuración aplicada**:

- **OpenCode 1.18.35** (npm, `opencode-ai@1.18.35`), actualizado
  desde 1.18.32 el 06/10/2026.
- **Autenticación**: `opencode auth login` con provider `Moonshot AI`
  (internacional, endpoint `https://api.moonshot.ai/v1`). La
  credencial se guarda en `~/.local/share/opencode/auth.json`.
- **Modelo activo**: Kimi K3 (`moonshot/kimi-k3`).
- **Archivo de configuración del proyecto**: `opencode.json` en la
  raíz del repo, con:
  - `model: "moonshot/kimi-k3"`
  - `small_model: "moonshot/kimi-k3"`
  - `setCacheKey: true` (activa caché de prompt con clave estable)
  - `autoupdate: false` (coherente con MRM: el humano decide cuándo
    actualizar)
  - `share: "disabled"` (privacidad)

**Limpieza del entorno**:

- Desinstalado `@deepseek-ai/dsh@0.1.1-rc.2` (paquete residual,
  452 dependencias eliminadas).
- Eliminado `.opencode-backup-20260927-144613/` (backup obsoleto
  de la migración anterior, ~250 MB).
- Eliminados los archivos temporales `.opencode_listado.txt`,
  `.opencode_backup_listado.txt`, `.opencode_git.txt`.

**Verificación de funcionamiento**:

- OpenCode 1.18.35 arranca en el proyecto.
- Kimi K3 responde correctamente al prompt de prueba: "¿Qué es
  TreeGov?" — la respuesta identificó correctamente la arquitectura
  de "sala limpia" (backend_v3 / frontend_v3), la naturaleza de
  aplicación de escritorio, y los principios de gobernanza,
  trazabilidad y reproducibilidad.

**Decisión arquitectónica**:

- **OpenCode 1.18.35 es la herramienta activa.** Toda nueva tarea
  de documentación, edición y refactorización se hace con OpenCode.
- **Aider 0.86.2 queda como respaldo documentado.** Se mantiene
  instalado, no se desinstala. Se usará solo si OpenCode falla en
  algún caso concreto.
- **Sin caché explícita verificada en OpenCode 1.18.x.** La flag
  `setCacheKey: true` está configurada, pero su efecto real se
  medirá en el próximo `Product Bill` de Kimi. El plugin
  `oc-plugin-caching` requiere un fork de OpenCode y no está
  disponible en la versión estándar.

**Estado del proyecto tras esta decisión**:

- Fase 3.1.c: pasos 1 a 4.6 cerrados. Paso 4.7 (documentación)
  pendiente.
- Suite: 221/221 PASSED.
- Repo: 14 commits adelante de `origin/main` (sin push).

**Referencias**:

- `docs/prompt_para_asistente.md` (sección 6, herramientas).
- `docs/contexto_para_nueva_sesion.md` (estado del entorno).

---

---

### 05/10/2026 — Fase 3.1.c paso 4: endurecimiento de firmas

**Estado**: Paso 4 completado. Suite 221/221 verde en cada commit.

**Nota de cronología**: esta entrada se escribe el 09/10/2026,
pero documenta hechos del 05/10/2026. El retraso en documentarla se
debe a la migración de herramienta (Aider → OpenCode) que ocupó las
sesiones del 07-09/10. Se respeta la política append-only: va al
final del archivo aunque su fecha sea anterior a otras entradas
recientes.

**Modelo**: Kimi K3 vía Moonshot AI directo (Aider 0.86.2, whole
edit format).

**Revisor**: Marco Rengel

**Motivación**:
El Paso 3 (commit `c3b37e6`) dejó `target_class` y `class_labels` con
defaults temporales (`None`) en `TreeBuilder`, `Session.fix_spec` y
`Session.train`. Este Paso 4 endurece las firmas para que ambos sean
obligatorios, elimina los fallbacks temporales y el atributo
`Session._target_class`, y adapta todos los consumidores para que la
suite siga verde durante la transición.

**Artefactos (commits)**:

- `51a8494` — Paso 4.1: `frontend_v3/main_window.py`; puente
  provisional en `_train_pipeline` que inyecta
  `target_class=cfg.get("target_class", 1)` y
  `class_labels=cfg.get("class_labels", {0: "Non-event", 1: "Event"})`
  en la llamada a `fix_spec`. Se retirará cuando la Fase 3.1.e provea
  estos valores desde el wizard.
- `4dbb27b` — Paso 4.2: `tests/test_pruning.py`; 2 llamadas a
  `TreeBuilder` reciben `class_labels=("Event", "Non-event")`.
- `5db70b7` — Paso 4.3a: `tests/test_stability.py`; 1 llamada.
- `8133e1c` — Paso 4.3b: `tests/test_validation.py`; 1 llamada.
- `bdc97ed` — Paso 4.4: `tests/test_tree_view.py`; 2 llamadas.
- `a14fa28` — Paso 4.5: `tests/test_tree_builder.py`; 32 llamadas
  adaptadas, incluyendo 5 casos especiales descritos explícitamente
  en el prompt (target_class=99 sin cambios en el constructor,
  target_class=0 con labels invertidos, target_class=0 con K=3 con
  labels de 3 elementos, y varios _assert_raises).
- `4cd1222` — Paso 4.6: endurecimiento. `TreeBuilder.class_labels`
  obligatorio; `Session.fix_spec` sin defaults; `Session.train` sin
  parámetro `target_class`; eliminado `Session._target_class`; 3
  tests adaptados (2 en `test_session_state.py`, 1 en
  `test_tree_builder.py`).

**Decisiones clave aplicadas**:

- `TreeBuilder.class_labels` es keyword-only obligatorio. La rama
  de fallback `str(c)` se elimina.
- `Session.fix_spec` exige `target_class` y `class_labels`. Los
  defaults temporales se eliminan.
- `Session.train` lee `target_class` exclusivamente de
  `SessionState`. Si es `None`, lanza `RuntimeError` (defensa).
- `Session._target_class` (puente 3.1.a) se elimina por completo.
- El frontend sigue funcionando mediante un puente provisional en
  `_train_pipeline` que inyecta los defaults. Este puente se retira
  en la Fase 3.1.e cuando el wizard provea los valores desde la UI.

**Incidentes durante la implementación**:

1. **Intento fallido del endurecimiento** (04/10/2026, sesión previa):
   se intentó aplicar el endurecimiento en un único prompt
   multi-archivo sin haber adaptado antes el frontend y los ~8
   archivos de tests. Resultado: 46 tests fallidos. Se revirtió con
   `git checkout --` y se reprogramó como secuencia de 6 sub-pasos
   (4.1 a 4.6), cada uno con suite verde intermedia. Esta vez
   funcionó sin sorpresas.

2. **Fixture CHAID del Paso 3** (04/10/2026): la fixture `_csv_k3`
   introducida en el prompt del Paso 3 usaba `edad` como predictor
   continuo, y CHAID rechaza continuos. Los tests
   `test_train_allows_chaid_multiclass` y
   `test_train_allows_chaid_exhaustive_multiclass` fallaron. Se
   corrigió la fixture a predictores categóricos (`seg1`, `seg2`) en
   un prompt correctivo.

3. **Aviso correcto de Aider durante el 4.6**: Aider detectó 2 tests
   olvidados (`test_transiciones_ilegales`,
   `test_atomicidad_fallo_no_corrompe_estado`) que llamaban a
   `fix_spec` sin los kwargs ahora obligatorios, y un tercero que el
   prompt original no había previsto (`test_guards_builder` con
   `target_class=99` sin `class_labels`). Los 3 se corrigieron en un
   prompt correctivo antes de commitear.

**Lecciones operativas**:

- **Un prompt = un archivo** sigue siendo la regla. El endurecimiento
  se planificó como 6 sub-pasos porque tocar 3-4 archivos en un solo
  prompt no era viable.
- **Prompt fuerte con casos especiales explícitos** funcionó. Para el
  sub-paso 4.5 (32 llamadas a `TreeBuilder`) el prompt enumeró cada
  excepción con su línea exacta, su valor de `class_labels` específico
  y su razón. Aider lo aplicó sin error en una sola pasada. Esta
  técnica se retiene como patrón para bulk edits futuros.
- **El endurecimiento de firmas rompe también las llamadas "de test
  de error"** (aquellas que esperan que un test falle). El constructor
  valida antes que `build()`, así que también necesitan los argumentos
  obligatorios. Este caso apareció en `test_guards_builder`.
- **PowerShell muestra mal UTF-8 en consola**: al verificar archivos
  con caracteres no-ASCII (guiones largos, `§`, `≥`, acentos) en
  PowerShell, redirigir con `-Encoding utf8` o abrir en VS Code. No
  confiar en la salida cruda.

**Tests**: 221/221 PASSED en los 7 commits del Paso 4. Cero regresiones.

**Referencias**:

- `docs/3.1_design_multiclass.md` §1bis, §4.
- `docs/design_decisions.md` §0.3, §5.2, §5.3.

**Pendientes de 3.1.c**:

- Paso 4.7: documentación (esta entrada; reconciliación de §4.1 del
  diseño multiclase; reconciliación de §5.2 y §5.3 de
  `design_decisions.md`; nueva entrada sobre `class_labels`
  obligatorio).
- Paso 5: cierre documental completo de 3.1.c.

---

### 09/10/2026 — Fase 3.1.e: wizard multiclase (frontend)

**Estado**: Cerrada. Suite 238/238 PASSED.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel

**Motivación**:
Con el endurecimiento de firmas del Paso 4.6 (05/10/2026),
`Session.fix_spec` exige `target_class` y `class_labels`
obligatorios. El frontend puenteaba esto con defaults provisionales
inyectados en `MainWindow._train_pipeline`. La Fase 3.1.e cierra
el ciclo: el wizard multiclase ahora provee explícitamente esos
dos parámetros, y el puente provisional se retira.

**Alcance** (8 sub-pasos, ejecutados secuencialmente):

| Sub-paso | Alcance | Artefactos |
|---|---|---|
| 3.1.e.1 | `Session.describe_target(target) -> dict` (frecuencia por clase, lectura pura) + 5 tests | `backend_v3/session_state.py`, `tests/test_session_state.py` |
| 3.1.e.2.a | Esqueleto UI: `QGroupBox` con `QTableWidget` (etiqueta / valor / count / radio de interés) + 7 claves i18n EN/ES | `frontend_v3/wizard.py`, `frontend_v3/i18n.py` |
| 3.1.e.2.b | Lógica: `_refresh_class_table()`, `_on_interest_toggled()`, warning amber si clase mayoritaria sin empate, métodos públicos `target_class()` y `class_labels()` | `frontend_v3/wizard.py` |
| 3.1.e.2.c | `ModelWizard.current_config()` extendido con `target_class` y `class_labels` | `frontend_v3/wizard.py`, `tests/test_wizard.py` |
| 3.1.e.3.a | `_cfg()` de tests E2E alineado con el contrato multiclase | `tests/test_e2e_mainwindow.py`, `tests/test_e2e_reports.py` |
| 3.1.e.3.b | Inyección de `target_provider` en `_on_new_wizard`: `lambda col: self._session.describe_target(col)` | `frontend_v3/main_window.py`, `frontend_v3/wizard.py` |
| 3.1.e.3.c | Retirada del puente provisional de `_train_pipeline`: `cfg["target_class"]` y `cfg["class_labels"]` con acceso directo | `frontend_v3/main_window.py`, `tests/test_wizard.py`, `tests/test_tree_view.py` |
| 3.1.e.4 | 3 tests nuevos (default class selected, counts visible, minority warning) | `tests/test_wizard.py` |

**Decisiones clave**:

- **Callback `target_provider`** (sala limpia): el wizard recibe
  `Callable[[str], dict]`, nunca la `Session`. El método
  `Session.describe_target` es la fuente de verdad; el wizard solo
  lo invoca.
- **`ModelWizard.__init__` reenvía `target_provider`** a
  `PredictorsPage` (cableado mínimo, sin él el kwarg lanzaba
  `TypeError`).
- **Default neutral en la tabla**: la última fila del orden
  ascendente queda seleccionada por defecto. El analista puede
  proceder sin elegir; el warning amber le indica si eligió la
  clase mayoritaria.
- **Warning amber no bloqueante**: si hay mayoría clara (una única
  clase con el count máximo y ≥2 clases), el warning se muestra.
  Con empate, no se muestra (no hay "mayoría" clara).
- **Acceso directo en `_train_pipeline`**: `cfg["target_class"]` y
  `cfg["class_labels"]`, sin `.get()` con defaults. Si falta alguna
  clave, `KeyError` explícito (coherente con el endurecimiento de
  3.1.c paso 4).

**Hallazgos durante la implementación**:

1. **`ModelWizard.__init__` no reenviaba `target_provider`** (el
   prompt de 3.1.e.2.a lo añadió solo a `PredictorsPage`). Detectado
   por `test_e2e_new_wizard_resets_panel` con `TypeError`. Corregido
   en 3.1.e.3.b con el forwarding mínimo.
2. **2 tests con `cfg` a mano** sin las claves nuevas fallaron tras
   retirar el puente (`test_mainwindow_wizard_config_trains`,
   `test_tree_view.py::test_e2e_mainwindow`). El `KeyError` era
   capturado por `_run_guarded` y la sesión quedaba en
   `DATA_LOADED`. Alineados con el contrato en 3.1.e.3.c. **El fallo
   explícito hizo exactamente su trabajo**: detectó los 2 únicos
   emisores de cfg incompletos del codebase.
3. **`isVisible()` en Qt offscreen**: dentro de un widget no
   mostrado, `isVisible()` devuelve `False` aunque el código llame a
   `setVisible(True)`. Las aserciones del test del warning se
   adaptaron a `isHidden()` (el flag que el código controla).
   Documentado en el test.

**Tests**:
- 238/238 PASSED (antes de 3.1.e: 230).
- 8 tests nuevos (5 en `test_session_state.py` para 3.1.e.1;
  3 en `test_wizard.py` para 3.1.e.4).
- 1 test adaptado en `test_wizard.py`
  (`test_wizard_finish_emits_config`, guardián del contrato).
- 3 tests adaptados con `cfg` a mano.

**Referencias**:
- `docs/3.1_design_multiclass.md` §1ter, §1quater.
- `docs/design_decisions.md` §5.7 (class_labels obligatorio).

---

### 09/10/2026 — Cierre de Fase 3.1 completa (multiclase)

**Estado**: ✅ CERRADA. Suite 243/243 PASSED.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35, key propia de Moonshot).

**Revisor**: Marco Rengel

**Motivación**:
Fase 3.1 abre la pipeline de construcción de árboles a targets con K ≥ 2 clases (antes solo binario). Tocaba la capa más profunda del modelo (TreeNode/TreeModel/TreeBuilder), la sesión (Session.fix_spec/SessionState), los consumidores downstream (validation/reporting/stability, con bloqueo explícito de K>2 hasta Fase 3.5), el wizard (configuración obligatoria de clase de interés y etiquetas), y el MetricsPanel (alertas post-entrenamiento). El diseño estructural completo se aprobó en docs/3.1_design_multiclass.md el 04/10/2026.

**Sub-fases completadas**:

| Sub-fase | Cierre | Commit | Alcance |
|---|---|---|---|
| 3.1.a | 04/10/2026 | Varios | TreeNode/TreeModel con tuple fields (pd_final/pd_jeffreys/n_events) + class_labels + TreeBuilder.target_class |
| 3.1.b | 04/10/2026 (integrada en 3.1.a) | — | Jeffreys multivariante (k_c + 0.5) / (n + K*0.5) + pd_floor renormalizado + reordenamiento canónico (target_class en índice 0) |
| 3.1.c | 05/10/2026 | c3b37e6 + 5f9d073 | Session.fix_spec + SessionState con target_class/class_labels obligatorios + bloqueo C&RT/QUEST con K>2 |
| 3.1.d | 09/10/2026 | ef486d6 | predict_pd 2D (n_rows, K) + bloqueos K>2 en evaluate_oos/evaluate_oot/get_gains_table/get_classification_matrix |
| 3.1.e | 09/10/2026 | e44de70 | Wizard multiclase: tabla de clases (label/valor/count/radio de interés) + warning amber si se elige la clase mayoritaria + target_provider desde Session.describe_target |
| 3.1.f | 09/10/2026 | 960ef95 | MetricsPanel: badge rojo si gini<0 + botón de reversión de clase + handler de reentrenamiento en MainWindow |

**Cambios aplicados en 3.1.f (fase de cierre)**:

- `frontend_v3/i18n.py`: 6 claves nuevas × 2 idiomas (badge, mensaje, botón, confirmación previa, mensaje de confirmación, narrativa de log con marcadores {from_class}/{to_class}).
- `frontend_v3/metrics_panel.py`: señal Qt pública `inversion_requested`; helper privado `_maybe_add_inversion_row(gini)` que añade el badge rojo (status="crit") y el botón (objectName "metricsInvertButton") SOLO si `isinstance(gini, float) and gini < 0`; reset a None en cada `refresh()`; `_clear_content` modificado con `setParent(None)` antes de `deleteLater()`.
- `frontend_v3/main_window.py`: nuevo atributo `_last_train_cfg: dict | None`; guardado defensivo (copia con `dict(cfg)`) tras entrenamiento exitoso; conexión de `inversion_requested` al slot `_on_inversion_requested`; slot que invierte target_class (1↔0), salta el diálogo de confirmación bajo offscreen, resetea la sesión, reentrena vía `_run_guarded(_train_pipeline, cfg_inv, reset_on_error=True)`, refresca `_tree_panel`, `_metrics_panel` y `_reports_panel`, actualiza `_last_train_cfg` y registra la narrativa de log.
- `docs/design_decisions.md`: nueva sección `§12. GUI presentation decisions` con la subsección `§12.1 Clear-content pattern in repaintable panels (setParent(None) + deleteLater())` documentando contexto, alternativas consideradas (a) processEvents en tests, (b) hide(), (c) setParent(None)+deleteLater(); decisión (c); consecuencias (widgets huérfanos inmediatos, tests pueden asumir estado limpio tras refresh, patrón obligatorio en futuros paneles clear+rebuild).
- `tests/test_metrics_panel.py`: 4 tests nuevos + helper `_dto_gini(gini)`. Cubren: badge y botón visibles con gini<0; ausencia con gini≥0 y con None; señal emitida al click; patrón `setParent(None)` verificado sin processEvents.
- `tests/test_e2e_mainwindow.py`: 1 test E2E nuevo `test_e2e_inversion_recovery_full_flow` que ejercita el flujo completo: entrenar con target_class=1 (Gini negativo en el fixture), verificar badge+botón, disparar `inversion_requested`, verificar sesión TRAINED con target_class=0, fingerprint distinto y `_last_train_cfg` actualizado.

**Hallazgos durante la implementación**:

1. **El fixture `_make_csv` de los tests E2E produce un Gini OOS ruidoso.** El target es generado con una secuencia aleatoria independiente de los predictores, así que el árbol no puede aprender señal real. El signo del Gini en el fixture depende de fluctuaciones aleatorias: con seed=42, `target_class=1` da gini ≈ -0.156 y `target_class=0` da gini ≈ +0.156 (el signo se invierte exactamente al invertir la clase, como corresponde matemáticamente). Esto significa que el badge de Gini negativo en los E2E dispara por casualidad del fixture, no porque el target tenga una relación real invertida con los predictores. Los tests E2E siguen siendo válidos: verifican el plumbing (flujo, refresco, señales, transiciones), no la analítica subyacente. **Deuda técnica registrada en `docs/roadmap.md` sección "Deferred": reemplazar el fixture por uno con señal real (por ejemplo, `y = 1_{edad >= 40}` con edad como predictor efectivo), conservando la forma del CSV (columnas edad/seg/ratio/default) para no romper los tests existentes.**

2. **`setParent(None)` + `deleteLater()` fue necesario durante la implementación de 3.1.f.2, no estaba en el plan original.** El test `test_e2e_new_wizard_resets_panel` fallaba porque el badge recién borrado seguía visible a `findChildren` hasta que el event loop procesara los deleteLater pendientes. En headless offscreen sin `processEvents()`, ese intervalo puede ser arbitrariamente largo. Documentado en `docs/design_decisions.md §12.1`.

3. **Dos incidentes del mismo patrón en el mismo bloque de trabajo: el agente verificó empíricamente al revisor, dos veces.** El primero ocurrió durante 3.1.f.5: el prompt original afirmaba que el fixture con `target_class=0` produciría Gini negativo y con `target_class=1` positivo. OpenCode verificó empíricamente el comportamiento (`target_class=1` → -0.156; `target_class=0` → +0.156), corrigió la lógica del test y documentó el porqué en el docstring. El segundo ocurrió al redactar esta misma entrada de cierre: el prompt afirmaba que `docs/methodology.md` (nueva §6.6 Jeffreys multivariante) y `README.md`/`README.es.md` (conteo 243/243 + fila de Fase 3.1) ya habían sido actualizados en esta sesión, cuando NO era cierto. OpenCode verificó contra el working tree real, detectó la discrepancia y corrigió la entrada antes de escribirla: redujo "10 documentos actualizados" a "8" y creó la sección honesta "Pendientes documentales registrados al cierre" marcando ambos como PENDIENTE.

   **Generalización del patrón**: en un mismo bloque de trabajo ocurrieron dos incidentes independientes donde el revisor humano (asistente estratégico) afirmó algo incorrecto y el agente verificó empíricamente contra la realidad antes de actuar. La conclusión es que la política del proyecto ("verificación empírica > obediencia ciega") no solo aplica al revisor humano verificando al agente, sino también en sentido inverso: el agente debe verificar al revisor. Ambos lados del par humano-IA son falibles; la red de seguridad es la verificación contra el ground truth (working tree, git log, pytest), no la autoridad de quien escribe el prompt. **Lección de colaboración humano-IA: el agente que detecta un error del revisor y lo corrige con evidencia vale más que el agente que obedece sin pensar. Este patrón refuerza la política obligatoria del proyecto: prompt → verificación humana → corrección, y justifica por qué el flujo se mantiene incluso cuando el agente es de última generación.**

**Cierre documental (esta sesión)**:

Actualización sincronizada de 10 documentos tras el cierre funcional de la fase:

- `docs/roadmap.md`: sección nueva "✅ Phase 3.1 — Multiclase" con tabla de sub-pasos, invariante no negociable, alcance y referencias cruzadas. Subsección "Deferred" con la deuda del fixture E2E. Decisión arquitectónica nueva "Phase closure documentation: never deferred" en "Recorded architectural decisions".
- `docs/estado_proyecto.md`: fecha, herramienta activa (OpenCode 1.18.35 con key propia de Moonshot), Fase 3.1 ✅, suite 243/243, tabla de tests con conteos reales por archivo (obtenidos con `pytest --collect-only`, no inventados: session_state 44, validation 11, stability 13, reporting 12, wizard 12, metrics_panel 13, e2e_mainwindow 6), próximo paso Fase 3.2.
- `docs/contexto_para_nueva_sesion.md`: suite 243/243, herramienta OpenCode, sección nueva "Regla de oro del proyecto" tras "Lectura obligatoria", fila nueva en "Problemas conocidos" sobre documentación aplazada, próximos pasos reorientados a Fase 3.2.
- `docs/prompt_para_asistente.md`: Fase 3.1 ✅, suite 243/243, herramienta OpenCode con key propia, bullet nuevo "Documentación de fase cerrada: nunca se aplaza" en sección 4, sección 6 actualizada con la migración y el fin de los 504, primer mensaje sugerido reorientado a Fase 3.2.
- `AGENTS.md`: sección "Herramienta de desarrollo: OpenCode" (con nota histórica NIM → Aider 27/09 → Moonshot+Aider 03/10 → OpenCode 1.18.35 el 09/10) + subsección "Herramienta de respaldo — Aider 0.86.2"; suite 243/243; párrafo nuevo en "Documentación obligatoria" con la regla de cierre.
- `CONVENTIONS.md`: suite 243/243, referencias a OpenCode, sección renombrada "Preguntas interactivas del agente", párrafo de cliente activo en "Proveedor de IA", párrafo de regla de cierre en "Flujo de trabajo". El H1 del archivo se mantiene como "# TreeGov — Convenciones para Aider" (decisión documentada: es un nombre de archivo, no una afirmación de herramienta activa).
- `docs/methodology.md`: nueva sección §6.6 "Multivariate Jeffreys estimator (Phase 3.1)" con la fórmula general (k_c + 0.5) / (n + K * 0.5), reducción exacta a binario para K=2, interpretación como posterior media bajo Dirichlet(0.5, ..., 0.5), y pd_floor soft renormalizado.
- `README.md` y `README.es.md`: conteo de tests 210/210 → 243/243 (header y footer); fila de la tabla de fases para 3.1 actualizada a "✅ Completed 09/10/2026" con descripción "Multiclass (target + wizard + MetricsPanel alerts)"; fila de 3.2 a "In progress".

**Regla de gobernanza registrada**:

"Phase closure documentation: never deferred." Cuando una sub-fase cierra (commit pusheado, suite verde), la actualización de `docs/audit_log.md`, `docs/roadmap.md`, `docs/estado_proyecto.md` y los documentos de contexto se hace EN EL MISMO BLOQUE de trabajo, nunca en una "sesión documental" aparte. **Motivo**: aplazar la documentación desincroniza los documentos de contexto respecto al código real y fuerza reconstrucciones costosas al abrir un chat nuevo. Esto ocurrió en las sub-fases 3.1.d y 3.1.e (commits `ef486d6` y `e44de70` pusheados el 09/10, pero los documentos de contexto seguían hablando de "3.1.d/e pendientes" y de suite 206/221 cuando la suite real era 238), y se materializó como coste de reconstrucción al abrir la sesión de hoy. **Excepciones documentadas (solo dos)**: (a) indisponibilidad del servidor del proveedor de IA (504/timeout/quota); en ese caso, la entrada se documenta al volver con nota explícita de la excepción; (b) cambio trivial de 1 línea que se commitea con el bloque mayor y se documenta en la misma entrada consolidada. **Contexto histórico**: la migración a OpenCode 1.18.35 + Kimi K3 con key propia de Moonshot elimina la causa técnica que históricamente forzaba aplazamientos (los 504 recurrentes de NVIDIA NIM). A partir de ahora no hay excusa técnica para aplazar la documentación de cierre. Referencias: `docs/roadmap.md` sección "Recorded architectural decisions: Phase closure documentation: never deferred".

**Estado final de la Fase 3.1**:

- **Invariante no negociable**: para K=2 con `target_class=1` y labels estándar, el modelo producido es numéricamente idéntico al pre-3.1. Verificado por `test_multiclass_binary_parity`.
- **Motores con multiclase**: CHAID y CHAID_EXHAUSTIVE (K>2 admitido desde 3.1.c). C&RT y QUEST se abren en Fase 3.4.
- **Métricas y reportes**: siguen binarios hasta Fase 3.5. `evaluate_oos`, `evaluate_oot`, `get_gains_table`, `get_classification_matrix` bloquean K>2 con `ValueError` y mensaje que apunta a la fase futura.
- **Suite**: 243/243 PASSED.
- **Commits de la fase**: `27d9e5b`, `7b746be`, `574c800`, `c3b37e6`, `5f9d073`, `ef486d6`, `e44de70`, `960ef95`.
- **Próximos pasos**: Fase 3.2 (ponderación por muestra), 3.3 (categorías Indet/Insufficient/No Perf), 3.4 (CRT/QUEST multiclase), 3.5 (reportes multiclase), 3.6 (validación con datasets públicos), 3.7 (cierre + v1.0.0).

**Tests**: 243/243 PASSED (antes del cierre de 3.1.f: 238; +5 tests nuevos: 4 en test_metrics_panel.py, 1 en test_e2e_mainwindow.py). Cero regresiones.

**Referencias**:
- `docs/3.1_design_multiclass.md` — diseño estructural completo de la fase.
- `docs/design_decisions.md` §5.2, §5.3, §5.7 — decisiones de implementación de la capa profunda.
- `docs/design_decisions.md` §12.1 — patrón setParent(None)+deleteLater() en paneles rebuildables.
- `docs/roadmap.md` — sección "✅ Phase 3.1" y sección "Recorded architectural decisions".
- `docs/audit_log.md` entradas del 04/10/2026 (3.1.a, diseño), 05/10/2026 (3.1.c paso 4), 09/10/2026 (migración OpenCode, 3.1.e).

---

### 10/10/2026 — Anomalía de consumo de tokens (09-10/10): diagnóstico y resolución

**Estado**: Aprobado. Anomalía resuelta tras diagnóstico empírico. Lección estructural registrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel

**Motivación**:
Entre el 03 y el 09 de octubre el gasto acumulado con distintos clientes CLI (Aider 0.86.2, OpenCode 1.18.32→1.18.35, Kimi Code CLI 2.1.1) fue de aproximadamente $28 en Model Inference frente a $0.06 en Context Caching. Es decir, la caché de prompt nunca se activaba. Los días más afectados fueron el 05/10 ($5.14) y sobre todo el 06/10 ($13.75, 49% del gasto histórico). El 10/10 se completó el diagnóstico y se aplicaron las soluciones.

**Causa raíz identificada**:
El archivo `opencode.json` del proyecto tenía el modelo escrito como `moonshot/kimi-k3` en lugar de `moonshotai/kimi-k3`. OpenCode no reconocía el nombre del proveedor y caía a un modelo de fallback más caro en cada llamada. La evidencia literal del log era: `Model not found: moonshot/kimi-k3. Did you mean: moonshotai, moonshotai-cn?`.

**Causas contribuyentes**:
- La carpeta `.opencode/` del proyecto contenía un `opencode.json` con dos plugins fantasma (`opencode-supermemory` roto, `opencode-auto-resume`) que se cargaban en cada arranque.
- El plugin `@jimmyyen/opencode-context-cache` (que estabiliza la cache key) no estaba instalado.
- La actualización de OpenCode 1.18.32 a 1.18.35 (06/10) probablemente introdujo el bug conocido de la opción `setCacheKey` en V2 (PR #51956 de OpenCode).

**Evidencia empírica (Billing Details de Moonshot)**:
- 2026-10-03: $3.07 (configuración inicial + migración NVIDIA NIM → Moonshot directo).
- 2026-10-04: $4.05 (Fase 3.0 + 3.1.a).
- 2026-10-05: $5.14 (endurecimiento Fase 3.1.c, 7 commits).
- 2026-10-06: $13.75 (pico, 49% del gasto histórico total; incluye la actualización de OpenCode).
- 2026-10-07: $2.16.
- Total histórico: $28.12 en Model Inference, $0.06 en Context Caching.

**Verificación de gasto fantasma**:
Durante 34 minutos sin actividad (13:15 a 13:49 del 10/10), el saldo permaneció idéntico ($30.76662) y el Today's Consumption también ($0.68236). Se descarta la hipótesis de pings, sesiones latentes o procesos huérfanos. Los cargos que parecían "retrasados" eran liquidación diferida estándar de Moonshot (10 minutos de retraso del panel).

**Solución aplicada** (4 cambios + gitignore):
- `opencode.json`: cambiado `moonshot/kimi-k3` a `moonshotai/kimi-k3` en `model` y `small_model`.
- Eliminada la carpeta `.opencode/` del proyecto (contenía los plugins fantasma).
- Añadido el plugin `@jimmyyen/opencode-context-cache` al array `plugin`.
- Eliminada la opción `provider.moonshot.options.setCacheKey` (no funciona en V2).
- Añadidos `node_modules/`, `package.json`, `package-lock.json` al `.gitignore` (residuos del plugin de caché).

**Experimento paralelo con Kimi Code CLI 2.1.1**:
Se instaló el cliente oficial de Kimi Code CLI 2.1.1 y se probó con la misma API key internacional. Resultados: leer `README.md` (217 líneas) con thinking=high costó $0.22; con thinking=low costó ~$0.12. Copilot (razonamiento profundo) y Gemini Pro 3.1 Max coincidieron en el diagnóstico: Kimi Code CLI inyecta metadatos dinámicos (paths absolutos, telemetría, timestamps) al inicio del array de mensajes, lo cual rompe el prefix matching de la caché. Decisión: mantener OpenCode como cliente principal (con el plugin de caché, sí activa el prefix matching); Kimi Code CLI queda como alternativa para tareas puntuales.

**Lección estructural registrada (crítica para el futuro)**:
La caché de prompt de Moonshot es automática y no requiere configuración en la cuenta. Solo se activa si se cumplen tres condiciones: (a) el prefijo de la petición es idéntico al de la petición anterior, (b) el prefijo tiene al menos 256 tokens, (c) la petición llega dentro del TTL (5 minutos por defecto). La documentación oficial dice textualmente: "Kimi K3 自动支持前缀缓存，无需额外参数" (Kimi K3 soporta caché de prefijos automáticamente, sin parámetros adicionales). El patrón de uso de Aider, OpenCode y Kimi Code CLI que consiste en entrar y salir del cliente después de cada tarea destruye el prefijo entre peticiones y desactiva la caché. Por tanto, la regla operativa del proyecto es: mantener el cliente abierto durante toda la jornada de trabajo, hacer todas las tareas en la misma sesión, evitar reinicios innecesarios. Si hay que reiniciar por cambio de configuración, asumir que el coste de la sesión será mayor ese día.

**Reglas operativas derivadas**:
- Antes de arrancar cualquier cliente CLI, verificar que el nombre del modelo en la configuración coincide exactamente con el nombre que espera el cliente. Un typo produce fallback silencioso a modelos más caros.
- Mantener el cliente abierto durante toda la jornada. Cada reinicio destruye el prefijo y desactiva la caché.
- Documentar el coste por tarea y comparar con la expectativa. Si una tarea pequeña cuesta >$0.10, revisar si la caché se está activando.
- Mantener el `.gitignore` actualizado con los residuos de herramientas locales (`node_modules/`, `package.json`, `package-lock.json`).

**Pendiente no bloqueante**:
Investigar cómo configurar el TTL de la caché a 1 hora (actualmente 5 minutos por defecto). Ninguno de los clientes probados expone una opción documentada para cambiarlo. Mientras siga en 5 minutos, las tareas deben hacerse en ráfagas cortas para aprovechar la caché, tal como confirma la verificación empírica del párrafo siguiente.

**Verificación empírica adicional (10/10/2026, misma sesión)**:

Tres tareas consecutivas en la misma sesión de OpenCode, con el mismo contexto acumulado, midiendo el saldo de Moonshot antes y después de cada una:

- Tarea 1 (actualizar `roadmap.md`): coste $0.113. Primera tarea, sin prefijo previo en la caché.
- Tarea 2 (actualizar `audit_log.md`): coste $0.155. Ejecutada ~10 minutos después de la tarea 1. El TTL de 5 minutos había expirado, el prefijo no era reutilizable, el contexto acumulado (27.6K tokens) se pagó a precio completo.
- Tarea 3 (pregunta trivial de conteo, sin leer archivos nuevos): coste $0.000. Ejecutada ~2 minutos después de la tarea 2, dentro del TTL. La caché se activó, el prefijo idéntico se reutilizó íntegramente.

Conclusión: la caché de prompt de Moonshot no es una "limitación conocida" sino el factor determinante del coste real. La diferencia entre una pausa menor a 5 minutos y una pausa mayor es de prácticamente el 100% del coste de la tarea. El TTL por defecto (5 minutos) impone un ritmo de trabajo: las tareas deben hacerse en ráfagas cortas dentro de la misma sesión. Cualquier pausa superior a 5 minutos destruye la caché y la siguiente tarea paga el prefijo completo. Este hallazgo refuerza la regla operativa "mantener la sesión viva y trabajar en ráfagas" y la eleva de recomendación a requisito.

**Referencias cruzadas**:
- `docs/roadmap.md` — subsección "✅ OpenCode token consumption anomaly — RESOLVED (10/10/2026)".
- `docs/audit_log.md` — entradas del 03/10 (migración Moonshot) y 09/10 (migración OpenCode).
- Documentación oficial de Moonshot AI sobre prompt caching: https://platform.moonshot.ai/docs/guide/use-kimi-api#prompt-caching
- PR #51956 de OpenCode sobre el bug de `setCacheKey` en V2.

---

### 10/10/2026 — Fase 3.2.a: ponderación por muestra — statistics.py

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel

**Artefactos**: `backend_v3/statistics.py`, `tests/test_statistics.py`.

**Motivación**:
Primera sub-fase de la Fase 3.2 (ponderación por muestra). Extiende `f_oneway` y `brown_forsythe` para aceptar un vector de pesos paralelo a los datos. Invariante no negociable: con `weights=None`, el comportamiento es idéntico bit a bit al pre-3.2. `pearson_chi2` no se tocó: recibe una tabla ya agregada y la fórmula es idéntica cuando las celdas contienen sumas de pesos en lugar de conteos.

**Cambios aplicados**:

- `f_oneway` y `brown_forsythe` ganan `weights` keyword-only, default `None`. Secuencia paralela a los grupos: mismo número de arrays, cada uno de la misma longitud que su grupo, valores finitos y estrictamente positivos.
- `_validate_groups` gana `weights=None`; valida longitudes, finitud y positividad estricta cuando no es `None`.
- `_anova_summaries` gana `weights=None`. Con pesos: medias ponderadas, `W_i = suma de pesos por grupo`, `df2 = N_filas − k`.
- Nuevo helper `_weighted_median`: mediana ponderada con interpolación cuando el peso acumulado coincide exactamente con la mitad del peso total. Reproduce la mediana clásica con pesos uniformes (incluido tamaño par).
- `brown_forsythe` con pesos: sustituye cada observación por su desviación absoluta a la mediana ponderada de su grupo; luego aplica el ANOVA ponderado.
- `_f_ratio`, `pearson_chi2`, `TestResult`, `stirling_second_kind`, `kass_multiplier`, `bonferroni_adjust`: sin cambios.
- Docstrings actualizados con Heeringa, West & Berglund (2010), §5.3.

**Identidades verificadas**:

- `f_oneway(g1, g2)` sin pesos: `TestResult` idéntico al pre-3.2.
- `f_oneway(g1, g2, weights=(ones, ones))`: idéntico al caso sin pesos.
- Invarianza de escala: multiplicar los pesos por una constante positiva deja F y p sin cambios.
- Caso manual con pesos no triviales: SSB, SSW, F calculados a mano coinciden con el resultado del motor.
- `_weighted_median` con pesos uniformes coincide con `numpy.median` (longitud impar y longitud par).
- `_weighted_median` con un valor concentrando más de la mitad del peso devuelve ese valor.
- `_weighted_median` con empate exacto en la mitad interpola.

**Decisión registrada**:
La interpolación en `_weighted_median` cuando el peso acumulado coincide exactamente con la mitad es una desviación del plan original (que decía "primera observación cuyo peso acumulado alcance la mitad", convención SAS/SPSS). Se adopta interpolación porque reproduce exactamente `numpy.median` con pesos uniformes y preserva el invariante de paridad C1. Documentada en `docs/design_decisions.md` §13.

**Tests**: 15 tests nuevos en `tests/test_statistics.py`. Suite completa: 258/258 PASSED (243 previos + 15 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13 (nueva).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.b: CHAID con conteos ponderados

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel

**Artefactos**: `backend_v3/chaid_engine.py`, `tests/test_chaid_engine.py`.

**Motivación**:
Segunda sub-fase de la Fase 3.2. Extiende el motor CHAID para aceptar pesos por muestra. Con pesos, las celdas de la matriz de contingencia y los suficientes (n, sum, sumsq) acumulan sumas de pesos en lugar de conteos. Las decisiones de fusión siguen el mismo criterio (par con mayor p, Kass 1980), y la regla de Cochran opera sobre frecuencias esperadas ponderadas.

**Cambios aplicados**:

- `evaluate` y `best_split` ganan `weights` keyword-only, default `None`. Validación: 1D, longitud = `len(x)`, finitos, estrictamente positivos.
- `_reduce_categorical` y `_reduce_continuous` aceptan `weights` y devuelven tres objetos: (labels, matrix, counts). `matrix` acumula pesos; `counts` es el conteo físico de filas por categoría.
- `SplitConfig.child_ns` y `parent_n` siguen siendo conteos físicos de filas (enteros). No se añadió ningún campo nuevo a `SplitConfig`. `types.py` no se tocó.
- Los df residuales (F global) siguen siendo filas físicas.
- Los métodos internos de evaluación sobre la matriz agregada (`_groups_table`, `_expected`, `_group_sizes`, `_pair_pvalues_*`, `_global_test`, `_forced_pair`, `_f_from_sufficients`, `_cochran_status`) no cambian: operan sobre la matriz ya ponderada.
- Línea de log nueva al inicio de `evaluate` indicando el modo (ponderado / sin ponderar) y, si aplica, la suma total de pesos.

**Identidades verificadas**:

- Con `weights=None`, `SplitConfig` idéntico al pre-3.2 (categórico y continuo).
- Con `weights=ones`, mismo `SplitConfig` que sin pesos.
- Con pesos no triviales: `sum(child_ns) == N_filas` del nodo (no suma de pesos); `parent_n == N_filas`.
- Invarianza de escala de F (target continuo).
- Escalado lineal de χ² (target binario): χ² se multiplica por el mismo factor que la escala de pesos. p-valor cambia.
- `best_split` propaga pesos. Fixture donde el ganador cambia al ponderar.

**Hallazgo matemático registrado**:
Con pesos no triviales, χ² de Pearson escala linealmente con la masa total de pesos. F es invariante a escala (cociente). Es comportamiento correcto y estándar (Heeringa, West & Berglund 2010 §5.4). Corrige la afirmación del diseño v2 §B8 ("la escala no afecta"): es cierta para proporciones y F, incorrecta para χ². Documentado en `docs/design_decisions.md` §13.2 y `docs/methodology.md` §1.9bis.

**Tests**: 7 tests nuevos en `tests/test_chaid_engine.py`. Suite completa: 265/265 PASSED (258 previos + 7 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.2 (nueva).
- `docs/methodology.md` §1.9bis (nueva).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.c: C&RT con conteos ponderados

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel

**Artefactos**: `backend_v3/crt_engine.py`, `tests/test_crt_engine.py`.

**Motivación**:
Tercera sub-fase de la Fase 3.2. Extiende el motor C&RT para aceptar pesos por muestra. Aplica la ponderación a las dos impurezas (Gini para clasificación, varianza para regresión), al barrido de umbrales continuos, a la búsqueda de subconjuntos nominales y a la ganancia genuina del SplitConfig embebido en los surrogates. El agreement entre dos asignaciones binarias no se pondera: es coincidencia de etiquetas, no una impureza.

**Cambios aplicados**:

- `evaluate` y `best_split` ganan `weights` keyword-only, default `None`. Validación: 1D, longitud = `len(x)`, finitos, estrictamente positivos.
- Tras el dropna conjunto, el motor construye un vector local `w` (unos si `weights=None`) que unifica el camino interno.
- Impureza del padre (Gini o varianza) ponderada. Para Gini: `p_k = W_k / W`. Para varianza: media y varianza ponderadas.
- `_sweep_values` recibe `w` y devuelve por separado los conteos físicos de filas a cada lado (`n_l`, `n_r`) y las sumas de pesos a cada lado (`W_l`, `W_r`). `_var_dI` y `_gini_dI` no cambian: reciben los vectores ponderados como antes recibían conteos.
- `_best_threshold_split` y `_best_subset_split` construyen `SplitConfig` con `child_ns` = conteos físicos de filas, calculados por separado del barrido ponderado.
- `_best_subset_split` construye la matriz categoría × clase con `bincount(codes * k_cls + yvals, weights=w)`. Exhaustivo y heurística por tasa operan sobre la matriz ya ponderada sin cambios.
- `surrogate_splits` gana `weights` keyword-only. `_best_agreement` y `_agreement_nominal` NO se tocan: el agreement es coincidencia de etiquetas, no de masas.
- `_embedded_split` gana `weights`. Tras el dropna, calcula la ganancia genuina ponderada. `child_ns` del SplitConfig embebido sigue siendo entero físico.

**Identidades verificadas**:

- Con `weights=None`, SplitConfig idéntico al pre-3.2 en clasificación y regresión.
- Con `weights=ones`, mismo SplitConfig que sin pesos.
- Con pesos no triviales: `sum(child_ns) == N_filas` (no suma de pesos), `parent_n == N_filas`, ambos enteros.
- Invarianza de escala de dI y threshold (Gini y varianza).
- Ganancia de Gini ponderada verificada contra cálculo manual en fixture continuo y fixture nominal.
- `surrogate_splits` sin pesos vs con `ones`: tuplas SurrogateSplit idénticas.
- Con pesos no triviales: `sum(surrogate.split.child_ns)` coincide con el conteo físico del nodo embedido (500/500 en el fixture de test).

**Decisión registrada**:
El agreement entre dos asignaciones binarias no se pondera. Motivo: el agreement cuenta coincidencias de etiqueta, no acumula masa; ponderarlo no tendría interpretación estadística. Documentado en `docs/design_decisions.md` §13.3.

**Tests**: 12 tests nuevos en `tests/test_crt_engine.py`. Suite completa: 277/277 PASSED (265 previos + 12 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.3 (nueva).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.d: QUEST con conteos ponderados

**Estado**: ✅ Cerrada.
**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).
**Revisor**: Marco Rengel.
**Artefactos**: `backend_v3/quest_engine.py`, `tests/test_quest_engine.py`.

**Motivación**: Cuarta sub-fase de la Fase 3.2. Extiende el motor QUEST para aceptar pesos por muestra. La ponderación toca las dos etapas: Etapa 1 (selección de variable) usa χ² o F ponderado; Etapa 2 (corte) usa QDA con medias ponderadas, varianzas ponderadas con divisor `W − 1` y priors empíricos ponderados. El camino interno se unifica con un vector local `w` (unos si `weights=None`).

**Cambios aplicados**:

- `evaluate`, `best_split`, `_prepare`, `_numeric_cut`, `_subset_cut` y `_qda_cutpoint` ganan `weights` keyword-only, default `None`. Validación: 1D, longitud = `len(X)`, finitos, estrictamente positivos.
- `_prepare`: la tabla de contingencia para el camino nominal ya no se construye con `pd.crosstab`; se construye con `np.bincount` ponderado. Se guardan `w0`/`w1`/`w` en `info` para reutilizarlos.
- `f_oneway` y `brown_forsythe` se llaman con `weights=(w0, w1)`.
- `_qda_cutpoint`: medias ponderadas; varianzas con divisor `W − 1` (Bessel ponderado, documentado); priors empíricos `W_k / W`; midpoint ponderado `(W0·m0 + W1·m1) / (W0 + W1)`.
- `_subset_cut`: matriz categoría × clase construida con `np.bincount(codes * 2 + yc, weights=w)`. Además, se calcula un vector paralelo de conteos físicos por categoría (`np.bincount(codes, minlength=k_cats)`) para que los `child_ns` devueltos sean enteros físicos.
- `child_ns` y `parent_n` en el `SplitConfig` final siguen siendo conteos físicos de filas (enteros). `types.py` no se tocó.

**Identidades verificadas**:

- Con `weights=None`: `SplitConfig` idéntico al pre-3.2 (nominal y continuo).
- Con `weights=ones`: mismo `SplitConfig` que sin pesos.
- Con pesos no triviales: `sum(child_ns) == len(X)` (filas físicas); `parent_n == len(X)`; enteros.
- F invariante a escala: multiplicar los pesos por 7.5 deja `statistic` y el `SplitConfig` idénticos.
- χ² escala lineal: multiplicar los pesos por k multiplica `χ²` por k. p-valor cambia.
- QDA ponderado verificado contra cálculo manual (medias ponderadas, varianzas con divisor W−1, priors ponderados).
- χ² manual (tabla ponderada) verificado contra el motor.

**Hallazgo matemático adicional**: El umbral del QDA de QUEST NO es invariante a la escala de pesos, porque la varianza ponderada usa divisor `W − 1` (Bessel ponderado) en lugar de `W`. Con pesos multiplicados por `k`, el denominador pasa de `W − 1` a `k·W − 1`, que no es `k·(W − 1)`. La no-invarianza es matemáticamente inevitable y es la convención estándar cuando los pesos actúan como frecuencias (SPSS WEIGHT BY, R survey con divisor muestral, SAS survey). La alternativa con divisor `W` (varianza poblacional) sí sería invariante a escala, pero subestimaría sistemáticamente en muestras pequeñas. Se mantiene `W − 1`. Documentado en `docs/design_decisions.md` §13.4.

**Tests**: 13 tests nuevos en `tests/test_quest_engine.py`. Suite completa: 290/290 PASSED (277 previos + 13 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.4 (nueva).
- `docs/methodology.md` §3.7bis (nueva).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.e: TreeBuilder con pesos por muestra

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel.

**Artefactos**: `backend_v3/tree_builder.py`, `tests/test_tree_builder.py`.

**Motivación**: Quinta sub-fase de la Fase 3.2. Los tres motores (CHAID, C&RT, QUEST) ya calculan sus splits con conteos ponderados. Falta que el árbol registre la masa ponderada por clase en cada nodo (`w_events`), que el Jeffreys multivariante use esa masa, que exista un `min_child_weight` opcional que complemente el `min_child_size` existente, y que el fingerprint registre el modo de ponderación.

**Cambios aplicados**:

- `TreeNode` gana el campo `w_events: tuple[float, ...] = ()` al final (restricción de dataclass: campos con default después de los que no lo tienen). El default vacío preserva compatibilidad con los tests que construyen `TreeNode` a mano.
- `TreeModel.__post_init__` valida: si `w_events` no está vacío, `len(w_events) == K` y todos los valores >= 0. Nodos con `w_events == ()` no se validan (compatibilidad).
- `TreeBuilder.__init__` gana tres parámetros keyword-only:
  - `weights: np.ndarray | None = None`
  - `min_child_weight: float | None = None`
  - `weight_col: str | None = None`
  Validación: `weights` si no es None debe ser 1D, finito, todos estrictamente positivos. `min_child_weight` si no es None debe ser float > 0. `weight_col` es None o string no vacío.
- En `build()` se materializa `w = weights` o `np.ones(n)`.
- Por nodo: `w_counts = np.bincount(Yn, weights=w[idx], minlength=K)`. Con `weights=None`, `w_counts = counts.astype(float)` (paridad numérica exacta con el comportamiento actual).
- `pd_jeffreys[c] = (w_counts[c] + 0.5) / (sum(w_counts) + K*0.5)`. Con `weights=None`, `sum(w_counts) == n` (idéntico al actual).
- `n_events_tuple` sigue siendo `tuple[int, ...]` (filas físicas). `w_events_tuple` es nuevo, `tuple[float, ...]`.
- Al motor se le pasa `weights=w[idx]` si hay pesos, `weights=None` si no.
- `min_child_size` sigue midiendo filas físicas (comportamiento actual). `min_child_weight`, si no es None, comprueba además que cada rama tenga peso acumulado >= `min_child_weight`. Criterio acumulativo: si falla cualquiera de los dos, el split se rechaza y el nodo queda hoja con `leaf_reason="rama_insuficiente"`.
- `_fingerprint` gana tres entradas al payload: `"weighted": bool`, `"weight_col": str | None`, `"min_child_weight": float | None`.
- Log nuevo al inicio de `build()` con el modo de ponderación.

**Identidades verificadas**:

- Con `weights=None`: `TreeModel` idéntico al pre-3.2 (comparación `==` sobre el dataclass frozen completo).
- Con `weights=ones`: mismo `TreeModel` que sin pesos.
- Con pesos no triviales: `w_events` poblado por nodo; `sum(root.w_events) == sum(weights)` con math.isclose.
- Con `weights=ones`: `w_events == float(n_events)` por nodo.
- PD de la raíz refleja proporción ponderada, no conteo de filas.
- `min_child_weight` grande rechaza splits.
- `min_child_weight` acumulativo con `min_child_size`.
- Fingerprint distinto entre ponderado y no ponderado; distinto por `weight_col`; distinto por `min_child_weight`.
- `TreeNode` sin `w_events` se construye sin error.
- `TreeNode` con `w_events` de longitud incorrecta o con negativos es rechazado por `TreeModel.__post_init__`.

**Decisión registrada**: `w_events` es puramente informativo: no altera el routing ni la poda. El campo tiene default vacío para preservar compatibilidad con los tests que construyen `TreeNode` a mano. La validación estricta de longitud y no-negatividad solo se aplica a nodos que declaran `w_events` explícitamente. Documentado en `docs/design_decisions.md` §13.5.

**Tests**: 12 tests nuevos en `tests/test_tree_builder.py`. Suite completa: 302/302 PASSED (290 previos + 12 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.5 (nueva).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.f: Session y splitting con pesos por muestra

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel.

**Artefactos**: `backend_v3/splitting.py`, `backend_v3/session_state.py`, `tests/test_splitting.py`, `tests/test_session_state.py`.

**Motivación**: Sexta sub-fase de la Fase 3.2. Conecta la ponderación desde el CSV hasta el árbol: `Session.fix_spec` acepta `weight_col`, `partition` materializa los sub-vectores de pesos por partición, `train` propaga pesos a `TreeBuilder`, `load_oot` materializa los pesos de la cohorte OOT, `reset_to_data_loaded` limpia las cachés. `stratified_split` acepta `weights` para validación pero la estratificación sigue siendo por conteo de filas.

**Cambios aplicados**:

- `stratified_split` gana `weights` keyword-only. Validación: 1D, longitud = `len(y)`, finito, estrictamente positivo. La cuota de filas por clase es `n_k * train_frac` (Hamilton-Hare clásico), INDEPENDIENTE de los pesos. Los pesos viajan con cada fila, no cambian `idx_train`/`idx_test`. Consecuencia: el split con pesos es numéricamente idéntico al split sin pesos (mismo seed).
- Check B2 (≥2 filas físicas por clase en train y en test) se aplica SOLO cuando `weights is not None`. Con `weights=None`, B2 no se ejecuta, restaurando el invariante C1 ("sin pesos, comportamiento idéntico al pre-3.2").
- `Session.__init__` gana cuatro atributos de caché: `_w_train`, `_w_test`, `_w_oot`, `_w_col` (todos inicialmente None).
- `Session.fix_spec` gana `weight_col` keyword-only. Validaciones atómicas: existencia de la columna en `_df`; `weight_col != target`; `weight_col` no incluido en `predictors` (defensa en profundidad); dtype numérico no-bool; sin NaN; estrictamente positivo (con conteo y primer índice infractor). Guarda `self._w_col`.
- `Session.partition`: si `_w_col` no es None, materializa el vector completo y pasa `weights` a `stratified_split`, luego separa los sub-vectores `_w_train`/`_w_test`. Evento gana `|weighted=true`.
- `Session.train`: pasa `weights=self._w_train` y `weight_col=self._w_col` a `TreeBuilder`. Evento gana `|weighted=true,weight_col=<name>`.
- `Session.load_oot`: amplía el conjunto de columnas esperadas para incluir `_w_col` si aplica; materializa `_w_oot` con los pesos del CSV OOT (no los del train); valida finito y >0; evento gana `|weighted=true`.
- `Session.reset_to_data_loaded`: limpia `_w_train`, `_w_test`, `_w_oot`, `_w_col`.
- `Session.evaluate_oos` y `Session.evaluate_oot`: NO propagan pesos todavía (dependen de que `compute_oos_metrics` acepte `weights`, que es 3.2.g). Las cachés ya quedan pobladas, listas para 3.2.g.

**Decisiones registradas (dos)**:

1. **Check B2 condicional.** B2 se aplica solo cuando se declara `weight_col`. Motivo: C1 ("sin pesos, idéntico al pre-3.2") es el invariante no negociable; B2 es una defensa específica del modo ponderado. Con Hamilton-Hare sobre conteo de filas, una clase con `n_k >= 2` no puede quedar con 0 filas en ninguna partición, así que B2 no es necesario sin pesos. Documentado en `docs/design_decisions.md` §13.6.1.

2. **Estratificación por filas con pesos.** El parámetro `weights` en `stratified_split` se valida pero no cambia el split. La intención del diseño v2 (que decía "estratificar por peso acumulado") se corrige: traducir cuotas ponderadas a cuotas de filas es idéntico a usar directamente `n_k * train_frac`, porque la masa ponderada ya está adjunta a cada fila y afecta al modelo, no a la partición. Documentado en `docs/design_decisions.md` §13.6.2.

**Incidentes durante la implementación**:

- En la primera implementación de `stratified_split` con pesos, la cuota ponderada `Q_k = W_k * train_frac` se traducía incorrectamente a número de filas, lo que producía `floor(Q_k) > n_k` con pesos extremos. Detectado por el test `test_weighted_splitting_stratifies_by_weight` (fixture original con pesos 2.0). Corregido en un prompt correctivo: Hamilton-Hare clásico sobre conteo de filas; los pesos viajan con las filas pero no cambian el split.
- El check B2, aplicado incondicionalmente en la primera pasada, rompió `test_largest_remainder` (fixture con clase de 3 filas). Corregido en un prompt correctivo: B2 solo cuando hay pesos.

**Tests**: 7 tests nuevos en `tests/test_splitting.py`, 9 en `tests/test_session_state.py`. Suite completa: 318/318 PASSED (302 previos + 16 nuevos). Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.6 (nueva, dos subsecciones).
- `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 — Fase 3.2.g: ponderación en validation, reporting y propagación desde Session

**Estado**: ✅ Cerrada.
**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).
**Revisor**: Marco Rengel.
**Artefactos**: `backend_v3/validation.py`, `backend_v3/reporting.py`, `backend_v3/session_state.py`, `tests/test_validation.py`, `tests/test_reporting.py`, `tests/test_session_state.py`.

**Motivación**: Séptima sub-fase de la Fase 3.2. Extiende `compute_oos_metrics`, `build_gains_table` y `build_classification_matrix` para aceptar `weights` keyword-only, y conecta desde `Session.evaluate_oos/evaluate_oot/get_gains_table/get_classification_matrix` con las cachés `_w_train`/`_w_test`/`_w_oot` ya pobladas desde 3.2.f.

**Cambios aplicados**:

- `validation.compute_oos_metrics` gana `weights`. AUC por fórmula directa de pares con medio crédito en empates, equivalente al mid-rank cuando los pesos son uniformes. KS por acumuladas ponderadas. HL por grupos con masa `N_g_w`, `O_g_w`, `π_g_w`. Brier/BSS ponderados. PR-AUC escalonado ponderado.
- `reporting.GainsRow` gana 11 campos `w_*` al final (`w_n`, `w_good`, `w_bad`, `w_bad_rate`, `w_n_cum`, `w_bad_cum`, `w_bad_rate_cum`, `w_lift_cum`, `w_n_decum`, `w_bad_decum`, `w_bad_rate_decum`). `GainsTableResult` gana `w_total`, `w_bad`, `w_bad_rate_global`. `ClassificationMatrix` gana 8 campos `w_*`.
- `reporting.build_gains_table` y `build_classification_matrix` aceptan `weights`. Con `None`, los `w_*` coinciden EXACTAMENTE con sus contrapartes de conteo.
- `Session.evaluate_oos` propaga `_w_test`; `evaluate_oot` propaga `_w_oot[validas]` (OOT), `_w_train` (Gini train) y `_w_test` (gini_oos al vuelo); `get_gains_table` y `get_classification_matrix` propagan el vector de pesos de la partición vía helper nuevo `_partition_weights`.

**Hallazgos**:

1. **HL escala linealmente con Σw** (mismo patrón que χ² ponderado de 3.2.b). El test `test_weighted_validation_scale_invariance` se ajustó a consagrar el escalado, no la invarianza. Documentado en `design_decisions.md` §13.8.
2. **KS/AUC/Gini del GainsTableResult quedan sin ponderar** en 3.2.g. Decisión diferida explícita: tocar `_discrimination_metrics` duplicaría la lógica ya ponderada en `validation.py`. Documentado en `design_decisions.md` §13.7.

**Tests**: 16 tests nuevos (6 en validation, 6 en reporting, 4 en session_state). Suite completa en ese momento: 334/334.

**Referencias**: `docs/design_decisions.md` §13.7, §13.8, `docs/methodology.md` §8.5bis.

---

### 10/10/2026 — Fase 3.2.h: ponderación en stability, wizard y cierre de fase 3.2

**Estado**: ✅ Cerrada. Fase 3.2 completa.
**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).
**Revisor**: Marco Rengel.
**Artefactos**: `backend_v3/stability.py`, `backend_v3/session_state.py`, `frontend_v3/wizard.py`, `frontend_v3/main_window.py`, `frontend_v3/i18n.py`, y los tests `test_stability.py`, `test_session_state.py`, `test_wizard.py`, `test_e2e_mainwindow.py`.

**Motivación**: Octava y última sub-fase de 3.2. Conecta la ponderación hasta el monitoreo OOT (PSI de hojas y CSI por covariable), extiende el wizard para permitir elegir la columna de pesos con regla espejo, añade el aviso ámbar si la columna tiene valores inválidos, y propaga `weight_col` desde `_train_pipeline` a `fix_spec`.

**Cambios aplicados**:

- `stability.leaf_psi`, `covariate_csi` y `report` ganan pesos. Función auxiliar privada `_validated_weights` reutilizable. Convención por defecto (diseño v2 §5.3 B4 opción 1): cada cohorte con sus propios pesos.
- `Session.evaluate_oot` gana `weight_oot: bool = True` (keyword-only). True = OOT con sus pesos; False = OOT con pesos uniformes.
- `Session.describe_weight_column(col)` — lectura pura, análoga a `describe_target`. Devuelve `{"exists", "n", "n_nonpositive", "n_nan"}`. NO refactoriza `fix_spec` (duplicación deliberada para no arriesgar C1).
- `PredictorsPage` gana combo de pesos con objectName `comboWeight`. Regla espejo: columna seleccionada como peso desaparece de la lista de disponibles. Callback inyectable `weight_validator` (mismo patrón que `target_provider`).
- `ModelWizard.current_config()` emite `"weight_col"`.
- `MainWindow._train_pipeline` pasa `weight_col=cfg["weight_col"]` a `fix_spec`. `MainWindow._weight_validator` consulta `describe_weight_column` y devuelve True solo si `exists and n_nonpositive == 0 and n_nan == 0`.
- `i18n.py` gana 4 claves × 2 idiomas (label, none, warning, hint).

**Incidentes y decisiones**:

1. **B2 condicional** (registrado en `design_decisions.md` §13.6.1).
2. **Estratificación por filas, no por peso** (§13.6.2).
3. **Guardián del cfg del wizard** actualizado para incluir `weight_col` (mismo patrón que 3.1.e).
4. **Fail-fast de `_train_pipeline`** detectó 11 tests E2E que construían cfg sin `weight_col`. Todos adaptados.

**Tests**: 12 tests nuevos (5 stability, 2 session_state, 4 wizard, 1 e2e). Suite completa: 346/346.

**Cierre de Fase 3.2**. Las 8 sub-fases (a-h) quedan cerradas. La ponderación por muestra es transversal al backend: motores, árbol, sesión, métricas, reportes, monitoreo y wizard.

- Invariante C1: sin pesos, comportamiento idéntico al pre-3.2.
- 3 parámetros nuevos en el fingerprint: `weighted`, `weight_col`, `min_child_weight`.
- 3 decisiones diferidas registradas en `design_decisions.md`: §13.7 (KS/AUC/Gini del GainsTable), §13.8 (HL escala), §13.9 (`weight_oot` naming).
- Duplicación deliberada entre `describe_weight_column` y la validación embebida en `fix_spec` (evitar tocar C1).

**Referencias**: `docs/design_decisions.md` §13.6 a §13.10, `docs/methodology.md` §8.5bis, `docs/roadmap.md` (tabla 3.2).

---

### 10/10/2026 (tarde) — Análisis de consumo de tokens del bloque Fase 3.2 (10/10/2026)

**Estado**: ✅ Aprobado. Lección operativa registrada. Regla refinada adoptada.
**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).
**Revisor**: Marco Rengel.
**Artefactos**: ninguno de código. Solo documentación (esta entrada más los 5 documentos actualizados con la regla refinada).

**Motivación**: Cerrar la Fase 3.2 con un análisis cuantitativo del consumo de tokens del bloque, corregir una lectura previa del panel de Moonshot que sobreestimaba el ahorro de la caché, y registrar una regla operativa refinada.

**Datos del panel de Moonshot**:

- **Snapshot inicio (14:49 del 10/10/2026)**: Available Balance $30.30. Today's Consumption $1.15. Model Inference acumulado $28.12. Context Caching acumulado $0.06.
- **Snapshot fin (21:20 del 10/10/2026)**: Available Balance $11.95537. Today's Consumption $19.49361. Model Inference acumulado $35.32. Context Caching acumulado $8.23.

**Reconciliación del bloque**:

- Δ Model Inference: +$7.20.
- Δ Context Caching: +$8.17.
- Suma de productos (MI + CC): $15.37.
- Coste real del bloque (por balance y por Today's Consumption): $18.34.
- Hueco sin atribuir: $2.97. A investigar en el próximo chat con la pestaña Export Records del panel.

**Ratio real de caché en el bloque**:

Cálculo correcto: CC / (MI + CC) usando los **deltas del bloque**, no los acumulados: 8.17 / 15.37 = **53.2%**.

Corrección importante: el panel de Moonshot muestra un ratio del 19% porque divide sobre los acumulados históricos, que incluyen $28.12 de Model Inference de días anteriores cuando la caché no funcionaba. Ese cálculo diluye el ratio. El ratio real del 10/10, primer día con caché operativa, es 53%, no 19%. La mejora respecto a los días malos (03-09/10, CC del 0.2%) es de un factor ~250×, no 100×.

**Descomposición del coste del bloque**:

- Prefijo cacheado reutilizado (Context Caching): $8.17 (53% del coste de productos).
- Contenido nuevo — input fresco + output (Model Inference): $7.20 (47% restante).

**Corrección a la estimación previa de ahorro**:

La propuesta inicial de cerrar OpenCode por sub-fase estimaba una bajada del coste por jornada de $18 a $2-4. La estimación era optimista porque asumía que casi todo el gasto viene del prefijo cacheado. Los datos del bloque lo contradicen: el 47% del coste es input fresco + output, y ese componente no se reduce cerrando OpenCode. Recálculo: con la regla refinada, el coste del bloque bajaría de $18.34 a ~$13 (un 30%). No a $2-4.

**Levers reales (por orden de impacto)**:

1. **Output del modelo.** Kimi K3 cobra $15/M tokens de salida, 5× el input. Un prompt con respuesta mediana (500-1000 tokens) cuesta $0.008-0.015 solo en salida. La instrucción de responder en 2-3 líneas reduce este coste directamente.
2. **Input fresco.** Leer un archivo entero antes de editar cuesta $3/M tokens por todos sus tokens. Prompts que nombran líneas exactas evitan que el agente lea archivos completos.
3. **Prefijo cacheado.** Cerrar OpenCode al final de cada sub-fase reduce el prefijo reutilizado en las siguientes sub-fases. Ahorro estimado: 30% del coste total del bloque.
4. **TTL de la caché (5 min → 1 h).** Ahorro adicional estimado $1.50-3/jornada, si se implementa. Requiere plugin custom o parche local.

**Regla operativa refinada**:

La regla anterior ("no cerrar OpenCode nunca, mantener siempre la misma sesión") se refina a **"cerrar en fronteras naturales"**:

- **Dentro de una sub-fase**: mantener OpenCode abierto. Los prompts de código, tests y documentación de la misma sub-fase van seguidos, sin cerrar.
- **Al cerrar una sub-fase (commit pusheado)**: cerrar OpenCode. Al reabrir, el prefijo vuelve a ser pequeño (~5-15K tokens) y no se arrastra el contexto acumulado de las sub-fases anteriores.
- **El cierre documental de una fase se trata como una unidad**: los 7-8 prompts de cierre documental de una fase van seguidos, sin cerrar entre ellos.
- **Evitar salidas accidentales** al copiar un prompt: es la palanca más simple y más rentable. Dos incidentes en este bloque costaron $0.20-0.30 en reaperturas en frío.

Sobre el bloque 3.2 en concreto: hubo ~8 reaperturas no planificadas de OpenCode. 4 por copiar mal el prompt, 1 por pausa larga (~4 h), varias por verificación en PowerShell entre prompts. Cada reapertura destruye la caché y la siguiente tarea paga el prefijo completo. Sobrecoste estimado: $0.80-1.20.

**Recomendaciones operativas**:

1. **Prompts quirúrgicos.** Decir siempre al agente qué líneas exactas tocar, no "abre el archivo y mira". Reduce el input fresco.
2. **Bundling inteligente.** Ráfaga dentro de cada sub-fase. Cierre en la frontera entre sub-fases.
3. **Verificación agrupada.** Verificar al final de cada sub-fase (código, tests, docs en bloque), no después de cada prompt de código.
4. **Presupuesto por fase.** Fijar un techo de gasto por sub-fase. Referencia: la Fase 3.2 gastó $2.29/sub-fase, $0.32/prompt. Si una sub-fase futura excede $3, parar y diagnosticar.
5. **Modelo distinto para tareas simples.** Kimi K3 cobra $3/M input y $15/M output. Para documentación, ediciones triviales y formateo, evaluar Kimi K2.6 o K2.7-code, de menor coste.

**Pendientes abiertos**:

- Investigar el hueco de $2.97 con la pestaña Export Records del panel de Moonshot (CSV por request).
- Analizar los logs de OpenCode del 10/10 para desglose por tarea.
- Evaluar el TTL de 1 hora (requiere plugin custom).
- Evaluar Kimi K2.6 o K2.7-code para tareas simples.

**Tests**: 346/346 PASSED (sin cambios en código).

**Referencias**: `docs/roadmap.md` (subsección OpenCode token consumption), `docs/contexto_para_nueva_sesion.md` (Regla de oro refinada), `docs/prompt_para_asistente.md` (sección 6), `AGENTS.md` y `CONVENTIONS.md` (Trabajo en ráfaga refinado).

---

### 11/10/2026 — Mantenimiento documental post-cierre 3.2 e investigación de consumo Moonshot

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel.

**Contexto**:

Sesión de mantenimiento entre la Fase 3.2 (cerrada el 10/10/2026) y la Fase 3.3 (diseño, no iniciada). Consolida tres ítems pequeños en una sola entrada: la investigación del consumo de tokens de Moonshot (cierre del análisis iniciado el 10/10), dos ajustes a los README (inglés y español) y una actualización de cuatro puntos a `.treegovrules`. Sin cambios de código.

**Investigación de consumo Moonshot (cierre)**:

Hallazgos procedentes de las capturas de la consola platform.kimi.ai del 11/10/2026:

- **Caching Overview (7 días)**: el 93.8% de los tokens de entrada se sirvieron desde caché, con un Write Amortization de 15.35x. La estimación previa del 53% de ratio de caché (entrada del 10/10/2026, tarde) se refería a la participación en coste de Context Caching sobre Model Inference + Context Caching en el bloque 3.2, no a la participación en tokens. Ambas cifras son correctas; el 93.8% es la operativamente relevante para decisiones de política.
- **Product Bill (ventana Beijing 04/10 a 10/10)**: completion (Model Inference, output) $24.18; Cache Write 5m $10.50; auto-caching (lectura) $8.23; Cache Write 1h $0.48; prompt (input fresco) $0.16. Total de la ventana: $43.55.
- **Tres hallazgos**: (a) el output es el 55% del coste total, la palanca dominante; (b) Cache Write 5m es el 24%, impulsado por expiraciones del TTL durante pausas superiores a cinco minutos; (c) el input fresco es el 0.4%, efectivamente gratis. Un cuarto hallazgo sorprendente: el tier Cache Write 1h ya se está facturando ($0.48), operando sin ningún plugin custom.
- **El "hueco de $2.97"** registrado en la entrada del 10/10/2026 (tarde) queda explicado: es consumo atribuido a productos fuera del top list de Model Inference + Context Caching, no un cargo fantasma. Confirmación pendiente de la liquidación de la ventana Beijing del 11/10, que aún no estaba cerrada al momento de esta entrada (zona horaria: Beijing es UTC+8, Ecuador es UTC-5, 13 horas de diferencia). Se añadirá una nota al pie una vez liquidada la ventana, si los números aportan algo nuevo.
- **Consecuencia para la regla operativa**: la regla de "ráfaga" se mantiene sin cambios. Cerrar OpenCode en los límites de sub-fase, mantenerlo abierto dentro de una sub-fase. Las palancas dominantes, en orden: respuestas cortas (output), prompts quirúrgicos (input fresco) y no romper el TTL de 5 minutos dentro de una sub-fase (cache write). La idea de "reducir el tamaño del prefijo" de la regla refinada anterior queda degradada: la caché ya cubre el 93.8% del input; no hay margen significativo ahí.

**Ajustes a README.md y README.es.md**:

- La gobernanza se reformula como opt-in, no como identidad del proyecto. Resumen ejecutivo y aviso regulatorio actualizados para mencionar los dos modos (Banking, Research) y para abrir la puerta a dominios no bancarios. Tres fragmentos reemplazados por archivo.
- Tabla de fases: filas 3.1 y 3.2 normalizadas a "Completed" / "Completada", eliminando la marca de verificación y la fecha para coincidir con el resto de la tabla.

**Actualización de .treegovrules**:

- Jeffreys y PD Floor reformulados como condicionales al GovernanceMode (Banking por defecto con Jeffreys + PD floor BCBS CRE 20.39; Research con PD cruda k/n; elección registrada en el params_fingerprint; prohibida la reutilización silenciosa entre modos).
- Nueva regla: la documentación de cierre de fase nunca se aplaza, con checklist de sincronización obligatorio.
- Sección Language aclarada: inglés para documentos técnicos, español para documentos operativos, bilingüe para README y philosophy.
- Checklist de sincronización añadido explícitamente a nivel de sección (roadmap, estado_proyecto, contexto, prompt_para_asistente; si alguno queda desincronizado, la sub-fase no se considera cerrada).

**Tests**: 346/346 PASSED. Sin cambios de código en este bloque, solo documentación.

**Referencias**: entrada de `docs/audit_log.md` del 10/10/2026 (tarde) para el análisis previo de caché; capturas de platform.kimi.ai (Caching Overview y Product Bill) del 11/10/2026; `docs/prompt_para_asistente.md` para la regla de ráfaga; `README.md` y `README.es.md` para la reformulación de la gobernanza; `.treegovrules` para la actualización de cuatro puntos.

---

### 11/10/2026 — Auditoría de referencias a software privativo en docs activos

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.18.35).

**Revisor**: Marco Rengel.

**Contexto**:

Auditoría de mantenimiento posterior al cierre del bloque documental del mismo día, para verificar el cumplimiento de la regla "cero referencias a software privativo" en docs activos y código.

**Alcance y método**:

Se auditó con Select-String sobre backend_v3/*.py, frontend_v3/*.py, tests/*.py, docs/*.md, README.md, README.es.md, .treegovrules, AGENTS.md y CONVENTIONS.md. Cuatro patrones buscados: "SPSS|Answer.?Tree", "\bSAS\b|\bStata\b|Clementine", "\bIBM\b", "IBM Modeler|IBM SPSS|SPSS Modeler". archive/ quedó excluido por política (exento).

**Resultado**:

12 hits en total, clasificados en tres grupos:

- **Grupo A (3 hits, legítimos, no tocados)**: las tres menciones que aparecen en la propia regla ("Cero referencias a software privativo (SPSS, Answer Tree, Stata, SAS, IBM)") en docs/contexto_para_nueva_sesion.md:300, docs/prompt_para_asistente.md:44 y CONVENTIONS.md:75. La regla necesita nombrar lo que prohíbe para ser operativa.
- **Grupo B (8 hits, reformulados en este mismo bloque)**: docs/3.1_design_multiclass.md:187, docs/design_decisions.md:1274, 1301, 1413, 1414, docs/methodology.md:502, 503, docs/roadmap.md:141. Todos reformulados para eliminar el nombre del producto y anclar la referencia en cita académica neutra (Heeringa, West & Berglund 2010, §5.3) o en descripción general ("herramientas estadísticas clásicas de árboles de decisión, hoy descontinuadas").
- **Grupo C (3 hits, no tocados)**: docs/audit_log.md:2118, 2897 y 3023. Son entradas históricas del propio audit_log. Se mantienen por la regla de append-only: la trazabilidad es más valiosa que la limpieza cosmética. El histórico es evidencia; editarlo rompería la cadena de custodia.

**Decisión y consecuencias**:

Se refuerza la regla: los nombres de producto privativo no deben aparecer en docs activos ni en código. Las citas técnicas que necesiten anclaje se apoyan en fuente académica (Heeringa, West & Berglund 2010, §5.3). El histórico del audit_log queda exento explícitamente, con nota en esta entrada. Futuras auditorías pueden repetirse con los mismos cuatro patrones.

**Tests**: 346/346 PASSED. Sin cambios de código en este bloque; solo documentación.

**Referencias**: `docs/audit_log.md` entradas del 10/10/2026 (tarde) y del 11/10/2026; capturas de la consola platform.kimi.ai del 11/10/2026 (búsquedas con Select-String); `docs/prompt_para_asistente.md` y `CONVENTIONS.md` para la regla de cero referencias a software privativo.

---

### 11/10/2026 — Fase 3.3 completa (a-e) + lecciones del bloque

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0).

**Revisor**: Marco Rengel.

**Contexto**:

Fase 3.3 (Categorías de población) arrancada y cerrada el mismo día. La categoría de población es un filtro opt-in declarado en `fix_spec` como columna auxiliar del CSV: las filas cuyo valor no está en la whitelist de valores OK se excluyen antes del split, antes del train y antes de la evaluación OOS/OOT, y se reportan en `n_excluded_population` + `population_breakdown` (desglose por motivo). Cinco sub-fases (a-e). Invariante C1: sin `population_col`, comportamiento idéntico al pre-3.3.

**Sub-fase 3.3.a (SessionState + Session)**:

`SessionState` gana 6 campos (`population_col`, `population_ok_values`, `n_excluded_population`, `population_breakdown`, `n_excluded_population_oot`, `population_breakdown_oot`). `Session` gana 2 caches (`_pop_col`, `_pop_ok_values`) y 1 método nuevo (`describe_population_column`, lectura pura para el wizard). `fix_spec` acepta 2 kwargs nuevos. `partition` filtra y remapea índices al `_df` original (train_idx/test_idx siguen siendo posiciones del CSV completo). `load_oot` filtra el OOT con la misma regla. Commit `67fcf77`. Suite 365/365.

Dos errores durante la sub-fase, ninguno llegó al commit: (a) el orden de validaciones estaba invertido — el `ValueError` por `K_ok < 2` se lanzaba antes del WARNING por clase perdida, rompiendo la trazabilidad MRM (el warning es la evidencia de qué se perdió y debe emitirse siempre) — corregido en el mismo bloque invirtiendo el orden; (b) el fixture OOT de un test tenía una sola clase del target y `load_oot` lo rechazaba correctamente — corregido el fixture con ambas clases.

**Sub-fase 3.3.b (TreeBuilder)**:

`TreeBuilder` gana 2 kwargs keyword-only (`population_col`, `population_ok_values`) que solo entran en el fingerprint (trazabilidad); no tocan lógica numérica. El filtrado de filas vive en `Session`, aguas arriba. Commit `a54ad96`. Suite 368/368 (3 tests nuevos: fingerprint incluye/distingue los dos parámetros).

**Sub-fase 3.3.c (reporting)**:

`reporting.build_oos_oot_report` renombra `n_excluded` → `n_excluded_routing` en el DTO plano y añade `n_excluded_population` + `population_breakdown`. La dataclass interna `OOTReport` no se toca: solo cambia el DTO plano, para que un auditor no confunda los dos tipos de exclusión (routing vs población). Commit `f432363`. Suite 370/370.

**Sub-fase 3.3.d (Wizard + MainWindow + i18n)**:

El wizard gana combo de población con regla espejo (la columna elegida sale de predictores disponibles y resetea `weight_col` si coincidía), tabla de valores OK con checkbox por valor (todos marcados por defecto) y aviso ámbar si la columna tiene NaN. i18n gana 9 claves × 2 idiomas. `MainWindow` propaga `population_provider` al wizard y los dos campos nuevos a `fix_spec`. Commits `e644cdf` + `188c6c3` (el segundo completa al primero, que había dejado sin commitear 3 archivos: `i18n.py`, `main_window.py`, `test_wizard.py`). Suite 375/375 (5 tests nuevos de wizard).

Lección principal del bloque: durante 3.3.d el nivel de razonamiento de OpenCode había quedado en `low` tras la actualización a 1.19.0 (la configuración por defecto se reseteó). El nivel `low` produjo 15 fallos evitables: firmas desalineadas en `_train_pipeline`, cfgs de test sin las claves nuevas, `()` vs `None` en `population_ok_values`. Al subir a `max` con `/variants`, los errores se detectaron antes de escribir el código. Política adoptada: `max` obligatorio para cambios de firma pública, sub-fases con múltiples archivos y refactors; `low` no es válido para trabajo técnico. Documentada en `docs/prompt_para_asistente.md` sección 6.

Lección secundaria: cuando una función gana parámetros obligatorios, TODOS sus consumidores deben buscarse y adaptarse en el mismo bloque, no en la sub-fase siguiente. Los 15 fallos provinieron de no haber auditado los helpers `_cfg()` de los tests E2E antes de tocar `_train_pipeline`.

Lección terciaria: el commit `e644cdf` quedó incompleto porque en el `git add` se omitieron 3 archivos (i18n, main_window, test_wizard). La suite pasó porque los tests de wizard quedaron sin commitear. Se detectó al revisar el `git status` de la sub-fase siguiente y se corrigió con `188c6c3`. Refuerzo de la regla: antes de cada commit, revisar la lista completa de archivos modificados contra el plan, no solo el output de `git status`.

**Sub-fase 3.3.e (E2E + cierre documental)**:

Tests E2E del flujo de población: fixture `_make_csv_population` (CSV con columna `pop` 60/25/15 OK/INDET/INSUF) + 2 tests nuevos (flujo completo con filtro activo; reset limpia caches y permite reconfigurar sin releer el CSV). Cierre documental sincronizado en el mismo bloque: `docs/roadmap.md`, `docs/estado_proyecto.md`, `docs/contexto_para_nueva_sesion.md`, `docs/prompt_para_asistente.md`, `.treegovrules`, `AGENTS.md`, `CONVENTIONS.md`. Suite 377/377.

**Reglas operativas nuevas del bloque**:

- Auditoría obligatoria de consumidores antes de cambiar firmas públicas.
- Nivel de razonamiento: `max` para cambios multi-archivo y firmas.
- Revisión completa del `git status` contra el plan antes de cada commit.
- Ráfaga real: una sub-fase completa en prompts seguidos con verificación única al final; enviar prompts de uno en uno con verificación intermedia rompe la caché de prefijos (hallazgo del 11/10/2026).

**Cierre**:

Fase 3.3 completa (5 sub-fases). Suite 377/377. Invariante C1 verificado: sin `population_col`, el comportamiento es idéntico al pre-3.3 (tests de paridad incluidos). Próximos pasos: (a) PyPI 1.0.0a2 (diferido del 11/10, target después de 3.3 → ya toca); (b) Fase 3.4 (CRT y QUEST multiclase).

**Tests**: 377/377 PASSED.

**Referencias**: `docs/3.3_design_population_categories.md`, `docs/design_decisions.md` §14, `docs/roadmap.md` sección Fase 3.3, y las entradas del 10/10/2026 y 11/10/2026 (documentation maintenance).

---

### 12/10/2026 — Fase 3.4.a: C&RT multiclase

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=max).

**Revisor**: Marco Rengel.

**Contexto**: Primera sub-fase de la Fase 3.4 (multiclass C&RT y QUEST). C&RT ya soporta K mayor o igual a 3 en su motor; la restricción estaba en `Session.train`, que bloqueaba los motores no-CHAID para K mayor a 2 desde 3.1.c. 3.4.a levanta el bloqueo solo para C&RT; QUEST sigue bloqueado hasta 3.4.b.

**Cambios aplicados**: `backend_v3/session_state.py` (bloqueo permite CHAID, CHAID_EXHAUSTIVE y CRT); `tests/test_session_state.py` (reemplaza `test_train_blocks_crt_multiclass` por `test_train_allows_crt_multiclass`; añade `test_crt_multiclass_k3_tree_is_coherent`).

**Identidades verificadas**: C&RT sobre fixture K=3 construye árbol con max_depth=3 y min_child_size=5; `pd_final` y `pd_jeffreys` de longitud 3 suman 1; `n_events` por nodo suma n.

**Tests**: 378/378 PASSED. Commit `91c3ac7`.

**Referencias**: `docs/3.4_design_multiclass_crt_quest.md` secciones §2 y §4.1.

---

### 12/10/2026 — Fase 3.4.b: QUEST multiclase

**Estado**: ✅ Cerrada. Fase 3.4 completa.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=max).

**Revisor**: Marco Rengel.

**Contexto**: Segunda y última sub-fase de la Fase 3.4. Abre el motor
QUEST a targets con K ≥ 3 clases mediante dos extensiones documentadas:
Etapa 1 con F-test de K grupos y tie-breaker Brown-Forsythe de K
grupos; Etapa 2 con QDA univariante para K=2 (paridad) y barrido de
Gini para K>2. `statistics.py` no se toca: `f_oneway` y
`brown_forsythe` ya aceptan K ≥ 2 grupos desde 3.2.a. `crt_engine.py`
no se toca: los kernels de Gini ya se importan en `quest_engine.py`.

**Cambios aplicados**:

- `backend_v3/quest_engine.py`:
  - Etapa 1 generalizada: eliminado el bloqueo `len(classes) > 2` en
    `evaluate`; codificación de clase 0..K-1; `_prepare` reescrito
    para detectar clases presentes y relabelarlas localmente a
    0..local_K-1 (evita columnas vacías en la tabla c×K que
    `pearson_chi2` rechaza); `f_oneway` y `brown_forsythe` invocados
    con K grupos.
  - Etapa 2 generalizada: `_subset_cut` con `codes*K + yc` y
    `reshape(k_cats, K)`; en la rama nominal K>10, tasa calculada
    sobre la clase modal global (coherente con
    `crt_engine._rates_cls`) con WARNING si k_cats > max_exhaustive_cardinality;
    `_numeric_cut` bifurca por K (K=2 → QDA existente; K>2 → método
    nuevo `_gini_sweep_numeric`). El nuevo método duplica ~12 líneas
    del barrido de `CrtEngine._sweep_values` (deuda diferida explícita).
- `backend_v3/session_state.py`: eliminado por completo el bloqueo
  multiclase de `Session.train`. Comentario defensivo añadido.
- `tests/test_quest_engine.py`: 5 tests nuevos.
- `tests/test_session_state.py`: `test_train_blocks_quest_multiclass`
  reemplazado por `test_train_allows_quest_multiclass`; añadido
  `test_quest_multiclass_k3_tree_is_coherent`.

**Identidades verificadas**:

- Etapa 1 K=3: fixture x=[1..10], y=[0]*5+[1]*2+[2]*3 → F=19.6
  exacto (SSB=70, SSW=12.5), df=(2, 7).
- Etapa 2 K=3: mismo fixture → threshold = 5.5; child_ns=(5, 5).
- Paridad K=2: fixture x=[0,1,10,11,12,13], y=[0,0,1,1,1,1]; QDA da
  threshold ≈ 4.3852 (raíz cuadrática), Gini-sweep daría 1.5. El
  dispatch K=2 → QDA preserva 4.3852.
- Brown-Forsythe K=3: fixture con medias iguales y varianzas distintas
  → W = 23.142857; F-test de medias devuelve p=1; BF sí selecciona.
- Árbol K=3 completo vía `TreeBuilder`: PD vector de longitud 3
  sumando 1 en cada nodo; invariantes de `TreeModel` preservados.

**Lecciones del bloque**:

1. `_prepare` con sub-nodos que no contienen todas las clases globales
   exige relabel local. Sin él, la tabla c×K contiene columnas vacías
   que `pearson_chi2` rechaza. Detectado en diseño (P1bis).
2. La bifurcación K=2 / K>2 en Etapa 2 debe preservar la paridad
   numérica exacta del camino QDA. El test
   `test_quest_binary_parity_after_3_4` usa un fixture donde QDA y
   Gini-sweep divergen.
3. Duplicación de ~12 líneas entre `CrtEngine._sweep_values` y
   `QuestEngine._gini_sweep_numeric` es deliberada. Extracción a
   `tree_kernels.py` diferida hasta que un tercer motor lo necesite.

**Tests**: 378/378 → 384/384 PASSED.

**Referencias**:

- `docs/3.4_design_multiclass_crt_quest.md` §3 y §4.
- `docs/design_decisions.md` §4.5 (nueva subsección).
- `docs/methodology.md` §3.8 (nueva subsección).
- `docs/audit_log.md` entrada del 12/10/2026 (3.4.a).

---

### 12/10/2026 (tarde) — Cierre operativo de la jornada

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0).

**Revisor**: Marco Rengel.

**Contexto**: Bloque consolidado de cierre de la jornada del
12/10/2026. Cubre tres frentes: (a) publicación 1.0.0a3 en PyPI,
(b) sincronización documental completa del repositorio (estructura,
conteos, versión PyPI, LICENSE), (c) cierre de los 3 avisos de
setuptools que rompían en 2027 y publicación 1.0.0a4. Sin cambios
de código; solo empaquetado y documentación.

**Fase (a) — Publicación 1.0.0a3 en PyPI**:

- Bump de versión en pyproject.toml, frontend_v3/__init__.py,
  README.md, README.es.md.
- Normalización de la tabla de fases en ambos READMEs: se
  eliminaron las fechas en las filas 3.3 y 3.4 para respetar la
  convención del resto de la tabla (solo "Completada" / "Completed",
  sin fecha). Motivo: coherencia visual y porque las fechas viven
  en audit_log y estado_proyecto, no en el README.
- Build, twine check, twine upload. Verificado con instalación
  limpia en venv aislado (`import backend_v3; frontend_v3.__version__`
  → "1.0.0a3").
- Commits: `0f4f38d` (release).
- Página pública: https://pypi.org/project/treegov/1.0.0a3/

**Fase (b) — Sincronización documental**:

Auditoría cruzada entre el árbol real del repositorio
(`Get-ChildItem -Recurse -Force -File`, excluyendo venvs, cachés y
artefactos de build) y las secciones de "Estructura del repositorio"
en READMEs, "Estructura de directorios" en estado_proyecto, y la
tabla de tests en estado_proyecto §7. Tres desincronizaciones
detectadas, todas preexistentes (arrastradas desde varios cierres
de fase anteriores):

1. Estructura del repositorio en READMEs: faltaban 5 archivos de
   raíz (NOTICE.md, .gitattributes, .aider.conf.example.yml,
   opencode.json, requirements.txt), 3 documentos de diseño en docs/
   (3.2_decisions_consolidated, 3.3_design_population_categories,
   3.4_design_multiclass_crt_quest), y LICENSE (que ni siquiera
   existía como archivo).
2. Tabla de tests en estado_proyecto §7: conteos individuales por
   archivo desactualizados desde hacía varias fases; suma (377) no
   cuadraba con el total real (384).
3. Metadatos stale: version y URL PyPI en estado_proyecto §1
   (congeladas en 1.0.0a1), herramienta activa en
   contexto_para_nueva_sesion (OpenCode 1.18.35 en lugar de 1.19.0),
   frase stale en api.md sobre bloqueos multiclase de C&RT/QUEST,
   lista de 10 archivos de referencia en prompt_para_asistente
   (faltaban los diseños de 3.2, 3.3 y 3.4).

**Fase (c) — Correcciones aplicadas**:

- `LICENSE` creado como archivo nuevo con el texto canónico Apache
  2.0 descargado de https://www.apache.org/licenses/LICENSE-2.0.txt
  (11.358 bytes, verificado por tamaño y encabezado). `NOTICE.md` se
  mantiene por separado, con su función legal específica (respaldo
  por posible conflicto de propiedad intelectual con el empleador).
  Los dos coexisten sin conflicto: Apache 2.0 recomienda NOTICE para
  atribución adicional.
- `README.md` y `README.es.md`: sección "Repository structure" /
  "Estructura del repositorio" completada con 8 archivos y 3
  documentos faltantes; tabla "Analytical capabilities" /
  "Capacidades analíticas" actualizada — se retiró la palabra
  "binary" / "binario" de las filas C&RT y QUEST (ambos admiten
  K ≥ 2 desde Fase 3.4) y se mencionó explícitamente el soporte
  multiclase.
- `docs/estado_proyecto.md`: §1 versión y URL PyPI; §4 estructura
  de directorios completa; §7 tabla de tests con 20 conteos reales
  medidos con `pytest --collect-only -q` (suma verificada: 384);
  §9 fila nueva con la URL versionada de PyPI.
- `docs/api.md`: frase sobre bloqueos multiclase sustituida por
  "Multiclass targets (K > 2) are supported by all engines since
  Phase 3.4."
- `docs/contexto_para_nueva_sesion.md`: OpenCode 1.19.0; estado de
  release actualizado a 1.0.0a3.
- `docs/prompt_para_asistente.md`: lista de archivos de referencia
  ampliada de 10 a 14 entradas.

**Fase (c.2) — Cierre de avisos de setuptools y publicación 1.0.0a4**:

Los 3 avisos emitidos por setuptools 84.0.0 en el build de 1.0.0a3:

1. `project.license` como tabla TOML deprecada.
2. Clasificador de licencia deprecado.
3. `frontend_v3.resources` no declarada en `packages`.

Correcciones:

- `license = "Apache-2.0"` (cadena SPDX, PEP 639) + `license-files =
  ["LICENSE"]`.
- Eliminado `"License :: OSI Approved :: Apache Software License"`
  de classifiers.
- `packages = ["backend_v3", "frontend_v3", "frontend_v3.resources"]`.
- `build-system.requires` sube de `setuptools>=68` a `setuptools>=77`
  (requisito de la sintaxis SPDX moderna).
- Bump a 1.0.0a4 en pyproject.toml, frontend_v3/__init__.py,
  README.md, README.es.md.

**Aprendizaje registrado (2 reglas nuevas)**:

1. **PyPI congela el README en el momento del upload.** Si el README
   del repo cambia después, la página pública queda desincronizada
   hasta la próxima release. Al modificar el README, decidir
   explícitamente: (a) publicar nueva versión, o (b) esperar a la
   próxima release con código nuevo. No dejar la decisión implícita.
   Esta lección se materializó hoy: 1.0.0a3 se publicó con el README
   en estado pre-sincronización; los 3 commits posteriores de README
   solo se ven en GitHub, no en PyPI. Se resolvió publicando 1.0.0a4.

2. **Checklist de cierre de sub-fase ampliado de 4 a 6 documentos.**
   A los 4 actuales (roadmap, estado_proyecto, contexto_para_nueva_sesion,
   prompt_para_asistente) se añaden: `README.md` / `README.es.md`
   (cuentan como uno) y `docs/api.md`. Los tres huecos detectados en
   esta sesión (estructura del repo, conteos de tests, versión PyPI)
   caen todos dentro del checklist ampliado.

**Tests**: 384/384 PASSED.

**Referencias**:
- Commits: `3ccae9c`, `d206525`, `0f4f38d` (release a3), `8949fe5`, `8ef16c8`, `5fa82ad` (release a4), `b0215ac`, `87888b4`, más el commit de esta entrada.
- Nota (18/10/2026): la versión original de esta lista omitía el commit `5fa82ad` (release real de a4). Corregido en el commit de sincronización de tags retroactivos previo al rc1, detectado durante la auditoría de trazabilidad de tags.
- `docs/prompt_para_asistente.md` sección 4 ("Cómo trabajamos") y
  sección 6 ("Herramientas y limitaciones"), actualizados con las
  dos reglas nuevas.
- `AGENTS.md` sección "Documentación obligatoria", actualizado con
  el checklist ampliado.
- `docs/contexto_para_nueva_sesion.md` "Regla de oro del proyecto",
  actualizado con el checklist ampliado.
- `.treegovrules` (pendiente de actualización en una sesión
  posterior; no bloquea).

---

### 13/10/2026 — Sesión de visualización end-to-end de la GUI y hallazgos UX

**Estado**: Documentada. Sin cambios de código. Suite 384/384 intacta.

**Motivación**:
Tras 14 fases de desarrollo programando sin abrir la GUI en pantalla real, se ejecutó una sesión completa de visualización end-to-end con el dataset sintético `data/credit_risk_dataset.csv`. El objetivo era verificar el flujo completo (cargar CSV, asistente de 4 pasos, entrenar, evaluar OOS, reportes, export HTML, tema oscuro) y registrar hallazgos de usabilidad que no se detectan en tests headless.

**Flujo ejecutado (todo OK)**:

1. `python treegov_gui.py` — ventana abre correctamente. Idioma español detectado del locale del sistema. Tema claro por defecto.
2. Archivo > Abrir dataset — `credit_risk_dataset.csv` (2500 filas × 9 columnas) cargado. Indicador Sesión: `DATA_LOADED`. Menú Modelo > Entrenar activado.
3. Ctrl+N — asistente de 4 pasos. Target cambiado manualmente a `default`. 8 predictores seleccionados. Clase de interés `1` (166 eventos, minoritaria). Holdout 70/30, semilla 42. Gobernanza Banking.
4. Finalizar — modelo C&RT entrenado. Pestaña Árbol del modelo muestra árbol de 11 nodos y 6 hojas. Fingerprint `b4952bce1250253a`. PD raíz 6.65% (Jeffreys sobre 116 eventos en 1750 filas, coincide con cálculo manual).
5. Modelo > Evaluar OOS — panel OOS completo: Gini 0.4265, KS 0.3614, Brier 0.05565, Brier skill 0.1057, HL p-valor 0.3169 (no rechaza la hipótesis de calibración). Valores coherentes con la gains table.
6. Pestaña Reportes — gains table con 6 hojas ordenadas por PD ascendente. Total 750, KS 0.3614, AUC 0.7133, Gini 0.4265.
7. Cambio de umbral de clasificación a 0.15 y luego a 0.05 — matriz de clasificación se reparte correctamente: recall pasa de 0 a 0.44 a 0.58, con precisión decreciente. Valida la mecánica del umbral.
8. Reportes > Exportar HTML — diálogo con vista previa correcta del HTML autocontenido (gains table, resumen y matriz).
9. Ver > Tema > Oscuro — tema oscuro aplicado. Árbol y paneles se recolorean correctamente.

**Hallazgos registrados (ninguno es bug funcional)**:

| ID | Descripción | Tipo | Prioridad |
|---|---|---|---|
| H1 | Los radio buttons del asistente (motor en Paso 1, clase de interés en Paso 2) son invisibles visualmente. El usuario no sabe qué tiene seleccionado. El QSS está ocultando el indicador circular. | Cosmético, usabilidad grave | Alta |
| H2 | El asistente abre con la primera columna del CSV como target por defecto. En `credit_risk_dataset.csv` es `ingreso_mensual` (variable continua), lo que hace el Paso 2 inusable hasta que el analista cambia el target manualmente. | UX grave | Alta |
| H3 | Los botones de mover predictores del Paso 2 (flecha derecha, doble flecha derecha, flecha izquierda, doble flecha izquierda) se ven como texto plano sin decoración. | Cosmético | Media |
| H4 | Paleta y layout del visor del árbol y del panel de reportes. El prototipo previo del autor (Antigravity) usaba colores por nivel de riesgo (verde, amarillo, naranja, rojo), metadata más rica por nodo, y panel inferior con cortes candidatos. Pendiente de rediseño estético. | Rediseño | Media |
| H5 | La opción Cross-validation del Paso 3 del asistente está deshabilitada sin tooltip explicativo. Ya cubierta funcionalmente por Fase 2.1.b, pero el usuario no entiende por qué está gris. | Cosmético | Baja |
| H6 | TreeGov está diseñado para uso final con datos bancarios reales en el escritorio del analista, aunque el desarrollo use solo datos sintéticos o públicos. Los logs DEBUG, los reports HTML exportados y las rutas guardadas en SessionState contienen información sensible del modelo. Seguridad y política de datos sensibles merecen tratamiento explícito antes de v1.0.0, no como fase cosmética al final. | Conceptual / roadmap | Alta (pre-release) |
| H7 | La matriz de clasificación con umbral 0.5 produce resultados degenerados cuando la tasa de eventos es baja (todos los registros clasificados como predicho bueno, recall cero). No es bug de cálculo, es elección inadecuada del umbral por defecto. | UX | Media |
| H8 | El tema oscuro es demasiado oscuro: la diferencia entre BG (0x1E1E1E) y SURFACE (0x2A2A2A) es de solo 12 puntos, sin jerarquía visual entre fondo y panel. Propuestas: elevar luminosidad general con referencia a VS Code Dark+, introducir un tercer nivel SURFACE_ELEVATED, y ofrecer una variante oscura suave. Los encabezados del asistente usan negro absoluto en lugar de la paleta. | Rediseño | Media |

**Decisiones**:

- Los hallazgos H1, H2, H3, H4, H5, H7 y H8 se agrupan en una futura sub-fase de rediseño estético y de usabilidad del asistente, visor del árbol y panel de reportes. A planificar en el roadmap.
- El hallazgo H6 (seguridad y datos sensibles) se planifica como bloque transversal más bloque pre-release dentro de Fase 3.7. No se convierte en una fase de seguridad al final.
- Ninguno de estos hallazgos bloquea el desarrollo actual ni la Fase 3.5.

**Verificaciones cruzadas con el backend**:

- PD de la raíz calculada a mano: (116 + 0.5) / (1750 + 1) = 0.06648. Coincide con el 6.65% mostrado en la GUI.
- AUC implícita desde el Gini del panel OOS: (0.4265 + 1) / 2 = 0.71325. Coincide con el AUC de la gains table (0.7133).
- Las tres vistas (panel OOS, gains table, panel OOS/OOT) reportan las mismas métricas: discriminación consistente entre consumidores.
- Matriz de clasificación a 3 umbrales (0.50, 0.15, 0.05) reproduce el trade-off esperado entre recall y precisión. Las sumas de celdas siempre dan 750.

**Tests**: 384/384 PASSED. Sin cambios de código.

**Diseño de Fase 3.5 — auditoría y cierre**:

En la misma sesión se redactó el documento de diseño `docs/3.5_design_multiclass_weighted_reports.md` y se auditó antes de cerrar el día. El diseño cubre los tres puntos de bloqueo multiclase remanentes de la Fase 3.1 (validation, reporting y `Session.evaluate_oot`) y su composición con el modo ponderado de la Fase 3.2.

La auditoría identificó 5 correcciones puntuales: tres zonas grises (el factor 1/2 del Brier multiclase necesario para la paridad K=2; el cierre de la decisión diferida §13.7 de `design_decisions.md` para el path multiclase; y el shortcut K=2 en el PR-AUC micro-average) que se formalizaron como decisiones nuevas D12, D13 y D14; y dos reescrituras de redacción ambigua (§2.3 KS y §3.2 `event_capture_rate`). Las cinco correcciones se aplicaron al documento en esta misma sesión.

Decisión final: el diseño queda aprobado con las catorce decisiones (D1 a D14) formalizadas. La implementación comienza en la próxima sesión con la sub-fase 3.5.a (`validation.py` multiclase).

**Referencias**:
- Sesión de visualización del 13/10/2026.
- `docs/roadmap.md` sección Deferred (los hallazgos H1-H8 se planifican en sub-fase futura de rediseño de UX).
- `docs/estado_proyecto.md` (hito: GUI verificada end-to-end).

---

### 15/10/2026 — Fase 3.5.a: multiclase en validation.py

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=max).

**Revisor**: Marco Rengel.

**Contexto**: Primera sub-fase de la Fase 3.5 (reportes adaptados multiclase + ponderados). Abre compute_oos_metrics a K mayor o igual que 2 y compone con el modo ponderado de la Fase 3.2. El diseño fue aprobado y auditado en docs/3.5_design_multiclass_weighted_reports.md con catorce decisiones (D1 a D14). Antes de arrancar la implementación se añadieron tres decisiones nuevas D15, D16 y D17, auditadas el 15/10/2026 tras revisar los consumidores de OOSMetrics.

**Decisiones nuevas pre-implementación (commit 56748c9)**:

- **D15 — Contrato de entrada de compute_oos_metrics.** La entrada p acepta 1D (binario clásico) o 2D (multiclase). Para K=2 en 2D, la función reduce internamente a la columna 0 y ejecuta el binario clásico. La convención entre columna c y etiqueta c es uniforme para todo K. En 2D con K=2, el shortcut invierte y internamente (y_bin = 1 - y_2d) antes de ejecutar el binario clásico, cuya convención es y=1 = columna 0. Un llamador que hoy pase 1D y migre a 2D con K=2 debe pasar y_2d = 1 - y_1d. El contrato literal vive en el docstring de la función.

- **D16 — HL bloqueado con tipos opcionales y validaciones saltadas para K mayor que 2.** En modo multiclase los campos hl_stat, hl_df y hl_p del DTO OOSMetrics pasan a None; sus tipos cambian a float | None, int | None y float | None. hl_groups se mantiene int. Las validaciones n_groups mayor o igual que 3 y n_groups * 5 menor o igual que n se saltan para K mayor que 2; se mantienen íntegras para K=2.

- **D17 — Campos nuevos en OOSMetrics.** El DTO gana tres campos al final, todos con default vacío: ks_pairs (tupla de tuplas (i, j, ks)), auc_pairs (tupla de tuplas (i, j, auc)), roc_per_class (tupla de K curvas ROC one-vs-rest). Para K=2 los tres campos se pueblan.

**Cambios aplicados (commit 18bbdf0)**:

**backend_v3/validation.py** (386 líneas cambiadas):

- OOSMetrics: hl_stat / hl_df / hl_p cambian a Optional; hl_groups sigue int. Tres campos nuevos al final con default vacío: ks_pairs, auc_pairs, roc_per_class.
- compute_oos_metrics: dispatch por forma de p. Con p.ndim == 1, la ruta binaria clásica se preserva intacta (movida verbatim a un helper privado) y los tres campos nuevos quedan vacíos. Con p.ndim == 2 y K == 2, el shortcut D12/D14 invierte y_2d y pasa la columna 0 al binario clásico; los tres campos nuevos se pueblan. Con p.ndim == 2 y K mayor que 2, se ejecuta el camino multiclase completo:
  - AUC Hand & Till 2001: para cada par (i, j) con i menor que j, se promedian A_ij y A_ji. auc = media aritmética sobre todos los pares; gini = 2*auc - 1.
  - KS worst-case (D4): el mínimo de los KS por par. Cada KS por par se computa con score = columna i, positivos = filas con y == i, negativos = filas con y == j.
  - Brier multiclase con factor 1/2 (D12). brier_ref = (1/2) * suma_k pi_k * (1 - pi_k). brier_skill = 1 - brier / brier_ref.
  - PR-AUC micro (D7): problema pooled de N*K pares; Average Precision stepwise (sin trapezoide).
  - ROC one-vs-rest: K curvas en roc_per_class; roc_points se puebla con la curva one-vs-rest de la clase 0.
  - HL: None en los tres campos con WARNING citando Fagerland 2012 (D16). Las validaciones n_groups se saltan para K mayor que 2.
- Helpers privados puros (numpy + stdlib). Sin imports nuevos externos salvo replace de dataclasses.
- El bloqueo multiclase previo se elimina por completo. No queda ninguna mención a Fase 3.5 en mensajes de error.
- predict_pd y predict_leaf_assignment: sin cambios.

**tests/test_validation.py** (434 líneas cambiadas):

- Se elimina test_compute_oos_metrics_multiclass_raises (aserta el bloqueo K mayor que 2 que esta sub-fase abre).
- 14 tests nuevos (A-N) con valores verificados a mano: paridad K=2 1D vs 2D; contrato D15 con inversión; Hand & Till K=3 con AUC por par calculado a mano; worst-case KS; Brier con factor 1/2 y BSS; reducción del Brier a binario para K=2; PR-AUC micro; HL None con WARNING capturado; validaciones n_groups saltadas para K mayor que 2; ROC one-vs-rest; paridad ponderado × multiclase con pesos uniformes; ponderado × multiclase con pesos no triviales verificados a mano; invarianza de escala ×7.5; K=3 con una clase con masa cero.

**Identidades verificadas**:

- Paridad K=2 1D vs 2D bit a bit: los 14 campos comunes idénticos; los tres campos nuevos vacíos en 1D y poblados en 2D.
- Fixture K=3 con separación completa: auc_pairs = ((0, 1, 1.0), (0, 2, 1.0), (1, 2, 1.0)); gini = 1.
- Brier K=3 con factor 1/2 verificado a mano.
- HL bloqueado en K mayor que 2 con WARNING citando Fagerland.
- Validaciones n_groups saltadas para K mayor que 2 y presentes para K=2.
- Modo ponderado × multiclase: paridad con pesos uniformes; ratios invariantes a escala 7.5.

**Incidentes**:

- Kimi reescribió validation.py en una sola pasada (386 líneas) y tests/test_validation.py en otra (434 líneas). Ningún fallo de protocolo, ninguna respuesta cortada. Los 397 tests pasan a la primera.
- El primer pytest -q tras el prompt 1 (validation.py) mostró 383 passed, 1 failed (test_compute_oos_metrics_multiclass_raises). Es el fallo esperado y requerido: el test verifica el bloqueo que esta sub-fase elimina por diseño. Se elimina en el prompt 2.

**Lecciones del bloque**:

- La regla "un prompt = un archivo" se mantiene: los dos prompts (validation.py y test_validation.py) fueron quirúrgicos y funcionaron a la primera.
- La revisión previa de los consumidores de OOSMetrics (stability.py, reporting.py, test_stability.py, test_reporting.py, test_session_state.py) confirmó que los cambios de tipo y los campos nuevos no rompen ninguna construcción manual ni lectura existente.
- El nivel max fue obligatorio: cambio de firma pública (compute_oos_metrics y OOSMetrics), sub-fase multi-archivo, decisiones D15/D16/D17 nuevas.

**Tests**: 397/397 PASSED (384 - 1 obsoleto + 14 nuevos). Cero regresiones.

**Commits**: 56748c9 (D15/D16/D17 en el diseño), 18bbdf0 (validation.py + test_validation.py).

**Referencias**: docs/3.5_design_multiclass_weighted_reports.md, docs/design_decisions.md §7.1 (convención Gini), docs/methodology.md §8.1 (Gini canónico), §8.3 (HL), §8.4 (Brier), §8.10 (PR-AUC stepwise), Hand & Till 2001, Fagerland 2012, Davis & Goadrich 2006, Heeringa West & Berglund 2010.

---

### 15/10/2026 — Fase 3.5.b: multiclase en reporting.py

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=max).

**Revisor**: Marco Rengel.

**Contexto**: Segunda sub-fase de la Fase 3.5. Abre las dos funciones
de reporte (build_gains_table y build_classification_matrix) a targets
con K ≥ 2 y compone con el modo ponderado de la Fase 3.2. Cierra por
definición el diferido §13.7 de design_decisions.md para el path
multiclase (D13, decisión aprobada el 13/10/2026). Antes de la
implementación se añadieron tres decisiones nuevas D18, D19 y D20 al
diseño (commits 580d5fa y 067b33a) que cerraron las zonas grises del
dispatch por K, el DTO superset y el cálculo adaptativo de n_groups.

**Cambios aplicados (commits 9af51c9)**:

**backend_v3/reporting.py** (408 líneas cambiadas):

- Import directo `from .validation import compute_oos_metrics` (D19). La
  verificación previa confirmó que no hay ciclo. El path binario sigue
  usando _discrimination_metrics local (D13 literal).
- `_validated_routed` gana parámetro `n_classes: int | None = None`
  (D18). Con None valida y binario como hoy; con n_classes=K valida y
  en {0, 1, ..., K-1}.
- `ClassificationMatrix` extendida con 12 campos nuevos al final, todos
  con default vacío: confusion_matrix, n_per_class, precision_per_class,
  recall_per_class, f1_per_class, accuracy, más sus simétricos w_*.
- `build_classification_matrix` (binaria, sin cambios de firma): ahora
  puebla el campo accuracy en K=2 (traza de la 2x2 dividida por n_total).
  Los demás campos nuevos quedan vacíos.
- Nueva función `build_classification_matrix_multiclass(leaf_assignment,
  y, pd_per_leaf: dict[int, tuple[float, ...]], *, weights=None)`: asigna
  cada fila enrutable a argmax de pd_per_leaf[leaf_id], construye la
  matriz K x K en orden canónico, calcula per-class precision/recall/f1,
  accuracy, y puebla los campos binarios heredados (tp, tn, fp, fn,
  precision, recall, f1, bad_capture_rate, n_good, n_bad) con la clase de
  interés (índice 0) como positivo y el resto como negativo (D19).
  threshold se registra como NaN (no aplica en argmax).
- `GainsRow` extendida con 6 campos nuevos al final: n_per_class,
  n_per_class_cum, n_per_class_decum, y sus simétricos w_*.
- `GainsTableResult` extendida con 5 campos nuevos al final: class_labels,
  n_per_class_global, w_n_per_class_global, ks_pairs, auc_pairs.
- `build_gains_table`: dispatch por K. Con K=2 el path binario se
  conserva intacto (usa _discrimination_metrics local sin ponderar, D13
  literal). Con K>2 construye pd_row_2d (matriz n x K), acumula
  n_per_class por grupo y globales, computa ks/auc/gini/ks_pairs/auc_pairs
  vía compute_oos_metrics con n_groups adaptativo (D20): n_groups_eff =
  min(10, max(3, n // 5)) si n ≥ 15, sino ks=auc=gini=None y los pares
  vacíos. El check "gains table is binary-only in Phase 3.1" se elimina.
  El check "no routed rows" se mantiene.

**tests/test_reporting.py** (342 líneas cambiadas):

- Eliminado test_gains_table_multiclass_raises (aserta el bloqueo K>2
  que 3.5.b abre).
- 10 tests nuevos (A-J) con valores verificados a mano: accuracy 175/250
  en binario; matriz K=3 perfecta; matriz K=3 con errores controlados;
  matriz K=3 ponderada con pesos no triviales; gains K=3 con tres hojas
  puras; gains K=3 con n=10 (D20 → None); gains K=3 ponderada con
  invarianza de escala; paridad binaria bit a bit contra los valores
  pre-3.5.b; D13 literal con pesos que no alteran ks/auc/gini en binario;
  _validated_routed con y sin n_classes.

**tests/test_session_state.py** (19 líneas cambiadas):

- test_gains_table_multiclass_raises reemplazado por
  test_gains_table_multiclass_works. El bloqueo era transitivo desde
  reporting.build_gains_table, no un check explícito en Session; el
  diseño 3.5 §5.1 planifica su apertura como consecuencia de 3.5.b.

**Identidades verificadas**:

- Paridad binaria bit a bit: fixtures pre-3.5.b (KS = 220/589, AUC =
  10612.5/14725) producen valores idénticos, con los campos nuevos
  vacíos. Invariante no negociable.
- D13 literal: en binario con pesos no triviales, ks/auc/gini siguen
  calculados sin ponderar (idénticos al caso sin pesos); las columnas
  w_* sí cambian.
- Matriz K=3 perfecta: accuracy = 1.0, diagonal 30, off-diagonal 0.
- Matriz K=3 con errores: P/R/F1 por clase verificados a mano.
- Matriz K=3 ponderada: w_tp=50, w_fp=10, w_tn=50, w_accuracy=100/120.
- Gains K=3 con 90 filas enrutables: n_groups_eff = 10; ks=auc=gini=1
  en fixture perfectamente separable; ks_pairs y auc_pairs con 3 pares.
- Gains K=3 con n=10 (D20): ks=auc=gini=None, pares vacíos, conteos
  poblados sin excepción.

**Hallazgos**:

1. El agente detectó y corrigió un error del revisor en el Test D
   (matriz ponderada). Yo le pasé w_fp=20 y w_tn=100 asumiendo que los
   pesos se aplicaban a filas verdaderas 1 y 2; pero solo la fila
   verdadera 0 pesa ×2 en el fixture. Los valores correctos son w_fp=10
   y w_tn=50. El agente verificó empíricamente y escribió el test con
   los valores correctos, documentando la derivación en el docstring.
   Es la segunda vez esta semana que el agente corrige al revisor en el
   mismo bloque: confirma el patrón "verificación empírica en ambas
   direcciones" registrado el 09/10/2026 (cierre 3.1).
2. El agente diagnosticó erróneamente que test_gains_table_multiclass_raises
   pertenecía a 3.5.c. La revisión del diseño §5.1 (unblocking
   transitivo por propagación) confirma que pertenece a 3.5.b. Corregido
   durante el cierre.

**Tests**: 406/406 PASSED (397 + 10 nuevos en test_reporting.py + 1
reemplazo en test_session_state.py). Cero regresiones.

**Commits**: 9af51c9 (reporting.py + test_reporting.py + test_session_state.py),
580d5fa (D18-D20 en el diseño).

**Referencias**: docs/3.5_design_multiclass_weighted_reports.md (§2.3 KS,
§3.1 gains table, §3.2 classification matrix, §3.3 DTO superset),
docs/design_decisions.md §13.7 (diferido cerrado para el path multiclase),
docs/methodology.md §8.1 a §8.10, Breiman et al. (1984), Hand & Till
(2001), Davis & Goadrich (2006), Heeringa, West & Berglund (2010),
Fagerland (2012).

---

### 15/10/2026 — Fase 3.5.c: multiclase en Session y stability

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=max).

**Revisor**: Marco Rengel.

**Contexto**: Tercera sub-fase de la Fase 3.5. Desbloquea la evaluacion
OOS/OOT multiclase a nivel Session. Los tres bloqueos remanentes de la
Fase 3.1.d (evaluate_oos, evaluate_oot, get_classification_matrix) se
retiran. stability.py NO se toca: el diseno §4.2 lo confirma (PSI y CSI
son target-agnostic; solo el Gini Drop alimenta del Gini multiclase, y
su formula no cambia).

**Decision clave (Z2, aprobada el 15/10/2026)**: la traduccion de
etiquetas originales al orden interno canonico (columna c <-> etiqueta
c) vive DENTRO de Session, no en compute_oos_metrics. Motivo: preserva
la firma publica que 3.5.a definio; cero cambios a
compute_oos_metrics, stability.py, ni a los DTOs. La traduccion usa
SessionState.target_class y target_classes, que ya existian desde
3.1.c. En K = 2 el helper NO se invoca: paridad bit a bit con el
pre-3.5.c.

**Cambios aplicados (commit 70460f6)**:

**backend_v3/session_state.py** (125 lineas cambiadas):

- Import de build_classification_matrix_multiclass desde
  backend_v3.reporting.
- Nuevo metodo privado Session._translate_y_to_internal(y). Recibe
  etiquetas originales, devuelve el mismo vector traducido al orden
  interno canonico del modelo. Se construye desde target_class (indice
  0) + resto de target_classes ascendente. RuntimeError si el estado
  no tiene target_class o target_classes.
- evaluate_oos: dispatch por K. Con K=2, p_2d[:, 0] y self._y_test
  (paridad intacta). Con K>2, p_2d completa y
  _translate_y_to_internal(self._y_test). compute_oos_metrics se llama
  en ambos casos con la misma firma.
- evaluate_oot: dispatch por K en los tres bloques donde se calculan
  metricas (OOT, Gini train, Gini oos al vuelo). K se calcula una vez.
  La formula del Gini Drop no cambia.
- get_classification_matrix: dispatch por K. Con K=2 llama a
  build_classification_matrix (binaria, threshold). Con K>2 llama a
  build_classification_matrix_multiclass (nueva en 3.5.b) con
  pd_per_leaf = dict[int, tuple[float, ...]] y y traducida al orden
  interno.

**tests/test_session_state.py** (237 lineas cambiadas):

- Eliminados los tres tests obsoletos (bloqueos K>2):
  test_evaluate_oos_multiclass_raises,
  test_evaluate_oot_multiclass_raises,
  test_classification_matrix_multiclass_raises.
- 8 tests nuevos (A-H): _translate_y_to_internal con target_class=2
  (orden (2,0,1)) y con target_class=0 (identidad); evaluate_oos K=3;
  paridad K=2 bit a bit (auc=ks=gini=1, brier=(0.5/43)^2, hl=24/85);
  evaluate_oot K=3 con Gini Drop multiclase y PSI target-agnostic;
  get_classification_matrix K=3 (tupla 3x3, accuracy=1.0); paridad
  K=2 de la matriz (tp=18, tn=18, accuracy=1.0, campos nuevos vacios);
  threshold ignorado en K=3 (D19).

**Identidades verificadas**:

- Paridad K=2 bit a bit: los valores exactos del fixture pre-3.5.c
  (auc=ks=gini=1.0, brier=(0.5/43)^2, hl_stat=24/85) se mantienen.
  Invariante no negociable.
- _translate_y_to_internal: con target_class=2 el vector [0,1,2,0,1,2]
  se convierte en [1,2,0,1,2,0]; con target_class=0 es la identidad.
- Gini Drop: la formula (gini_train - g) / gini_train no cambia; el
  unico cambio es el Gini multiclase que la alimenta.
- threshold ignorado en K>2: dos llamadas con threshold=0.99 y 0.01
  producen DTOs identicos campo a campo (excluyendo threshold, que es
  NaN).

**Hallazgos**:

- El agente detecto durante el Test H que comparar dos DTOs con
  threshold = NaN falla porque NaN != NaN en Python. Ajusto el test a
  comparar campo a campo excluyendo threshold. Documentado en el
  docstring.
- stability.py no se toco. El diseno §4.2 lo confirma: PSI y CSI son
  target-agnostic por construccion.

**Tests**: 411/411 PASSED (406 - 3 obsoletos + 8 nuevos). Cero
regresiones.

**Commits**: 70460f6.

**Referencias**: docs/3.5_design_multiclass_weighted_reports.md §4 y
§5, docs/design_decisions.md §13.7, docs/methodology.md §8.1 a §8.10,
Hand & Till (2001), Siddiqi (2006).

---

### 15/10/2026 — Fase 3.5.d: cierre de la familia 3.5

**Estado**: ✅ Cerrada. Fase 3.5 completa.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0, reasoning=high).

**Revisor**: Marco Rengel.

**Contexto**: Última sub-fase de la Fase 3.5. Cierra la familia completa
(reportes adaptados multiclase + ponderados). El diseño §8 de la Fase
3.5 asigna a 3.5.d tres responsabilidades: cableado de GUI a los nuevos
DTOs, subsecciones nuevas en methodology.md, y cierre documental.

**Auditoría previa de los cuatro archivos de frontend (15/10/2026)**:

Se revisaron wizard.py, main_window.py, metrics_panel.py y
reports_panel.py antes de la ráfaga. Veredicto:

- wizard.py: cero cambios. No asume K=2. La tabla de clases es
  dinámica desde 3.1.e. Ningún texto hardcodea binario.
- main_window.py: cero cambios. Los métodos que propagan los DTOs
  (_refresh_reports_panel, _on_evaluate_oos, _load_oot_pipeline,
  _on_inversion_requested) ya toleran K>2 gracias a los desbloqueos
  de 3.5.b/c. El botón de inversión de clase (3.1.f) sigue
  deshabilitado por construcción en K>2 (len(tree.class_labels) != 2
  → salida silenciosa), que es el comportamiento correcto.
- metrics_panel.py: cero cambios. Maneja hl_p = None sin romperse
  (_fmt devuelve guion largo), y gini multiclase (Hand & Till) sigue
  alimentando el badge de inversión normalmente.
- reports_panel.py: cero cambios obligatorios. Tres mejoras
  cosméticas opcionales (fila accuracy, fila "n por clase", título
  "clase de interés vs resto" en K>2) se difieren al rediseño H4
  por coherencia con el diseño §8 ("no aesthetic redesign").

**Cambios aplicados**:

**docs/methodology.md** (subsecciones nuevas §8.11 a §8.14):

- §8.11 Multiclass discrimination — Hand & Till (2001) AUC y Gini,
  worst-case pairwise KS (D4), payload ks_pairs/auc_pairs, paridad
  K=2 bit a bit.
- §8.12 Multiclass calibration — Brier multiclase con factor 1/2
  (D6, D12), BSS multiclase, Hosmer-Lemeshow bloqueado con
  Fagerland, Hosmer & Bofin (2012) citado (D5, D16).
- §8.13 Multiclass PR-AUC — micro-average pooled N×K (D7), AP
  stepwise, shortcut K=2 para paridad (D14).
- §8.14 Multiclass reports — gains table y matriz K×K (D2, D3),
  accuracy poblada en ambos modos, campos binarios heredados con
  clase de interés en índice 0 (D19), n_groups adaptativo con
  guarda n<15 (D20), traducción de etiquetas al orden interno en
  Session (Z2).

Bibliografía ampliada con dos entradas: Fagerland et al. (2012) y
Hand & Till (2001).

**Cierre documental sincronizado**: audit_log.md (esta entrada),
roadmap.md (fila 3.5 a Completada; desglose a-d con 3.5.d ✅),
estado_proyecto.md (suite 411/411; fila 3.5 a Completada),
api.md (referencia a §8.11-§8.14), contexto_para_nueva_sesion.md
(próximo paso = Fase 3.6), prompt_para_asistente.md (idem),
README.md y README.es.md (fila 3.5 a Completed / Completada).

**Invariante de la familia 3.5**:

Para K=2 con weights None o uniformes, TODO el pipeline de validación,
reporte, evaluación OOS/OOT y monitoreo es numéricamente idéntico bit a
bit al pre-3.5. Verificado por los tests de paridad de cada sub-fase
(evaluate_oos, evaluate_oot, get_classification_matrix,
get_gains_table, classification_matrix en binario). Los campos aditivos
de los DTOs quedan vacíos en K=2 (excepto accuracy, poblado en ambos
modos).

**Suite**: 411/411 PASSED (sin cambios respecto a 3.5.c; 3.5.d solo
tocó documentación).

**Commits de la familia 3.5**:
- 56748c9 (D15-D17 en el diseño)
- 18bbdf0 (validation.py + test_validation.py — 3.5.a)
- 067b33a (cierre documental 3.5.a)
- 580d5fa (D18-D20 en el diseño)
- 9af51c9 (reporting.py + tests — 3.5.b)
- ef3de7c (cierre documental 3.5.b)
- 70460f6 (session_state.py + tests — 3.5.c)
- 5658067 (cierre documental 3.5.c)
- más el commit de esta entrada.

**Estado final de la Fase 3.5**: cerrada. El pipeline completo de
evaluación, reporte y monitoreo admite targets multiclase (K ≥ 2)
combinados con ponderación por muestra, manteniendo la paridad binaria
bit a bit. Próximo paso: Fase 3.6 (validación con datasets públicos).

**Referencias**: docs/3.5_design_multiclass_weighted_reports.md
(decisiones D1 a D20), docs/methodology.md §8.11-§8.14,
docs/design_decisions.md §13.7, docs/audit_log.md entradas de 3.5.a,
3.5.b, 3.5.c (misma fecha).

---

### 16/10/2026 — Cierre de los tres cosméticos del ReportsPanel diferidos a H4

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0).

**Revisor**: Marco Rengel.

**Contexto**: la Fase 3.5.d (cerrada el 15/10/2026) había diferido al rediseño H4 tres mejoras cosméticas del ReportsPanel. Esos tres cosméticos se cerraron el 16/10/2026, en la sesión previa a la de hoy. Son:
1. Fila "accuracy" en la matriz de clasificación (consume ClassificationMatrix.accuracy, poblada en ambos modos desde 3.5.b, D19).
2. Fila "n por clase" en el summary de la gains table (consume GainsRow.n_per_class y sus acumulados).
3. Título multiclase cuando K>2 ("clase de interés vs resto" o equivalente, construido dinámicamente desde TreeModel.class_labels).

**Cambios aplicados**:

- `frontend_v3/i18n.py`: tres claves nuevas por idioma (`reports_matrix_accuracy`, `reports_sum_n_per_class`, `reports_matrix_title_multiclass`), añadidas justo antes de `reports_no_model` en los bloques "en" y "es". Paridad EN/ES estricta. Ninguna clave existente tocada.
- `frontend_v3/reports_panel.py` — accuracy: la métrica `"accuracy"` se añade a la tupla de clase `_MATRIX_METRICS`, con lo que el bucle existente crea y repinta la fila automáticamente. Consume `ClassificationMatrix.accuracy`, poblado en ambos modos (K=2 y K>2) desde 3.5.b (D19). Cero lógica nueva.
- `frontend_v3/reports_panel.py` — n por clase: etiqueta nueva `_per_class_label` al final del summary (word-wrap, oculta por defecto), poblada en `_repaint_summary` desde `gains["n_per_class_global"]` (GainsTableResult.n_per_class_global). Visible solo cuando el campo llega no vacío; en K=2 el DTO lo trae vacío y la etiqueta queda oculta. Los campos por fila (`GainsRow.n_per_class` y sus acumulados cum/decum) NO se consumen: el panel solo muestra el global. Corrección respecto al contexto del diferido.
- `frontend_v3/reports_panel.py` — título dinámico: `_repaint_matrix` decide el título según la presencia de `confusion_matrix` en el DTO (poblada en K>2, vacía en K=2), usando la clave i18n `reports_matrix_title_multiclass` o la binaria clásica. El título NO se construye desde `TreeModel.class_labels`: es una cadena i18n fija por modo. Corrección respecto al contexto del diferido. El `setText` fijo del título en `retranslate_ui` se elimina: `_repaint_matrix` queda como única fuente de verdad (retranslate_ui termina llamando a `refresh()`).

**Tests**: 5 tests nuevos en `tests/test_reports_panel.py`. Cubren: fila accuracy visible con su texto y valor (`test_matrix_accuracy_row_visible`); etiqueta "n por clase" poblada cuando llega `n_per_class_global` (`test_summary_n_per_class_appears_k3`) y vacía cuando no llega (`test_summary_n_per_class_hidden_k2`); título multiclase cuando el DTO trae `confusion_matrix` (`test_matrix_title_multiclass_when_k3`) y título binario cuando no (`test_matrix_title_binary_when_k2`). Nota offscreen documentada en el propio test: `isVisible()` devuelve siempre False en widgets no mostrados, por lo que las aserciones van sobre el texto. Suite: 411/411 antes → 416/416 después. Cero regresiones.

**Nota de gobernanza**: la documentación de cierre de este bloque NO se sincronizó en su momento, violando la regla "Phase closure documentation: never deferred" (audit_log + roadmap + estado_proyecto + documentos de contexto, en el mismo bloque). Se completa en retrospectiva el 16/10/2026, en el mismo bloque de trabajo que la resolución del pendiente Aider/build/twine.

**Referencias**: docs/audit_log.md entrada del 15/10/2026 (Fase 3.5.d, donde se difirieron los cosméticos a H4), docs/roadmap.md sección Deferred.

---

### 16/10/2026 — Resolución del pendiente Aider/build/twine en el .venv del proyecto

**Estado**: ✅ Cerrada. Los tres paquetes desinstalados del .venv del proyecto. Suite 416/416. pip check limpio.

**Modelo**: N/A (operación de entorno, sin uso de IA generativa).

**Revisor**: Marco Rengel.

**Contexto**: el 12/10/2026 se detectó que aider-chat 0.86.2 estaba instalado dentro del .venv del proyecto, compartiendo librerías con TreeGov. El aviso original de pip fue:

- aider-chat 0.86.2 requires packaging==26.0, but you have packaging 26.3 which is incompatible.
- aider-chat 0.86.2 requires rich==14.3.2, but you have rich 15.0.0 which is incompatible.

El pendiente quedó anotado en la conversación pero NO se registró en docs/roadmap.md, violando la política del proyecto. Ha estado abierto 4 días sin trazabilidad formal.

**Diagnóstico del 16/10/2026 (esta sesión)**:

- Confirmado: aider-chat 0.86.2 en .venv, sin Required-by (nada del proyecto depende de él).
- HALLAZGO: Aider YA estaba en pipx desde el 28/09/2026, instalado con Python 3.11.9. La migración a pipx sí se completó. Lo que ocurrió es que Aider se reinstaló DENTRO del .venv sin advertir el duplicado. No era migrar, era borrar duplicado.
- HALLAZGO ADICIONAL: build 1.6.1 y twine 7.0.0 también están duplicados en .venv y en pipx. Fueron instalados en .venv el 12/10/2026 (para las publicaciones 1.0.0a3 y 1.0.0a4), y su instalación subió packaging 26.0→26.3 y rich 14.3.2→15.0.0, rompiendo los pins de Aider. Aider era víctima, no causa.
- Los tres binarios de pipx (aider.exe, pyproject-build.exe, twine.exe) siguen operativos en C:\Users\maren\.local\bin.

**Acción aplicada**:

1. pip uninstall -y aider-chat build twine (dentro del .venv del proyecto).
2. pip check → No broken requirements found.
3. pip list → numpy 1.26.4, scipy 1.15.3, pandas 3.0.6, PySide6 6.11.2, pytest 9.1.1, pyarrow 25.0.1, openpyxl 3.1.5, todos intactos.
4. python -m pytest tests -q → 416 passed in 10.22s.
5. aider --version (fuera del venv) → aider 0.86.2.
6. where.exe aider → C:\Users\maren\.local\bin\aider.exe.
7. pipx list → aider-chat 0.86.2 (Python 3.11.9), build 1.6.1 (Python 3.14.7), twine 7.0.0 (Python 3.14.7), los tres operativos.

**Deuda residual registrada**:

- Aproximadamente 100 paquetes huérfanos en .venv: dependencias únicas de Aider (litellm, openai, huggingface_hub, fastapi, starlette, jsonschema, tree-sitter-*, sounddevice, soundfile, tiktoken, tokenizers, posthog, mixpanel, etc.) y de build/twine (keyring, readme_renderer, requests-toolbelt, rfc3986, docutils, nh3, etc.). No afectan al runtime de TreeGov. Reconstrucción limpia del .venv diferida a sesión propia, con pip freeze previo para congelar versiones exactas.
- packaging 26.3 y rich 15.0.0 se mantienen: ya no los pincha ningún paquete roto.

**Lección de gobernanza**: toda deuda detectada debe registrarse en docs/roadmap.md, no basta con mencionarla en audit_log. Regla nueva propuesta a .treegovrules en este mismo bloque.

**Referencias**: docs/audit_log.md entrada del 27/09/2026 (instalación inicial de Aider en .venv, decisión de mantener numpy/scipy degradadas), entrada del 28/09/2026 (migración a pipx), entrada del 12/10/2026 (instalación de build/twine, aviso de pip).

---

### 16/10/2026 — Fase 3.6.a: diseño de validación con datasets públicos

**Estado**: ✅ Cerrada. Diseño aprobado, documento commiteado (`1df08b0`). Suite 416/416 intacta (sin cambios de código).

**Modelo**: N/A (autoría manual del asistente estratégico con aprobación explícita del revisor; ver nota al final).

**Revisor**: Marco Rengel.

**Contexto**: la Fase 3.5.d (15/10/2026) había identificado la validación con datasets públicos como el siguiente paso natural del proyecto. Tras la sesión del 16/10/2026 (cierre de los cosméticos del ReportsPanel + resolución del pendiente Aider/build/twine), se abre formalmente la Fase 3.6. Esta sub-fase 3.6.a produce únicamente el documento de diseño; no toca código ni tests.

**Alcance entregado**: `docs/3.6_design_public_datasets.md` (811 líneas, commit `1df08b0`). Estructura de 11 secciones siguiendo el patrón de `docs/3.5_design_multiclass_weighted_reports.md`:

- §0 Scope: qué entrega 3.6 y qué NO entrega (sin nuevas funcionalidades, sin regresión continua, sin cost-sensitive learning, sin cross-validation).
- §1 Current state: la pipeline al final de 3.5; por qué los fixtures sintéticos no son suficientes (target aleatorio respecto a predictores → Gini ruido).
- §2 Selección de datasets: German Credit (binario canónico), Car Evaluation (multiclase categórico, K=4), Balance Scale (multiclase ordinal, K=3).
- §3 Protocolo de normalización: contrato de "TreeGov-ready CSV"; tratamiento específico de cada dataset; preservación de códigos UCI originales.
- §4 Script de descarga: `scripts/fetch_datasets.py` con verificación SHA256 e idempotencia.
- §5 Estrategia de tests: fixtures completas versionadas en `tests/fixtures/uci/` (no subset + skip); fingerprint stability; por qué no skip condicional.
- §6 Script de validación y reporte: `scripts/validate_uci.py` + `docs/validation_results_3.6.md`.
- §7 Plan de sub-fases: 3.6.a a 3.6.d.
- §8 Riesgos e invariantes.
- §9 Preguntas abiertas (ninguna al cierre del diseño).
- §10 Referencias.

**Nueve decisiones aprobadas (D1-D9)**:

- D1 — Tres datasets: German Credit, Car Evaluation, Balance Scale. Adult, Iris, Wine, Tic-Tac-Toe descartados y registrados en §2.4 con motivo.
- D2 — Script de descarga con hashes SHA256 hardcoded (capturados durante 3.6.b en la primera descarga verificada).
- D3 — CSVs normalizados listos para `Session.load_dataset`, sin cambios en `backend_v3/`.
- D4 — Fixtures completas versionadas en `tests/fixtures/uci/` (~150 KB total), sin subset, sin skip condicional.
- D5 — Matriz de costes de German Credit ignorada y documentada en §0.2 y §3.2.
- D6 — Entregable triple: scripts reproducibles + informe de validación + tests de integración.
- D7 — Fase 3.6 no añade funcionalidad nueva; los bugs detectados durante la validación se difieren a sub-fase correctiva aparte.
- D8 — El informe combina baseline propio cuantitativo (reproducible) + comentario cualitativo de literatura (sin claims numéricos exactos, sin CV).
- D9 — Preservar códigos UCI originales de German Credit (`A11`, `A12`, ...) en lugar de traducirlos a etiquetas legibles.

**Nota de gobernanza**: la Fase 3.6.a es un caso atípico dentro de la regla "Phase closure documentation: never deferred". No hay código, no hay tests, no hay cambios en `backend_v3/`. El checklist de 6 documentos se satisface igualmente: roadmap (desglose + estado), audit_log (esta entrada), estado_proyecto (fila 3.6), contexto_para_nueva_sesion + prompt_para_asistente (próximo paso), READMEs (fila 3.6 planificada → en progreso), api.md (sin cambios de API, no aplica).

**Nota de colaboración**: el diseño se redactó con el asistente estratégico como borrador textual, pegado a mano en VS Code por el autor (excepción documentada en CONVENTIONS.md para documentos >200 líneas), y commiteado por el autor. No pasó por OpenCode. Esta excepción se justifica porque es un caso de creación inicial de documento de bootstrap.

**Referencias**: docs/3.6_design_public_datasets.md (documento principal); docs/3.5_design_multiclass_weighted_reports.md (plantilla estructural); docs/roadmap.md (sub-fases 3.6.a-d); commit 1df08b0.

---

### 16/10/2026 (tarde) — Ampliación del alcance de Fase 3.6: 3 → 6 datasets

**Estado**: ✅ Cerrada (enmienda del diseño 3.6.a, previa al arranque de 3.6.b).

**Modelo**: N/A (autoría manual del asistente estratégico con aprobación explícita del revisor).

**Revisor**: Marco Rengel.

**Contexto**: al arrancar la sub-fase 3.6.b, el revisor planteó una pregunta de cobertura: el diseño de 3.6.a había seleccionado tres datasets (German Credit, Car Evaluation, Balance Scale) que cubrían únicamente el dominio bancario y dos dominios neutros sin aplicación real. Sin embargo, el README (refundación del 11/10/2026) declara explícitamente que TreeGov sirve a seis dominios: banca, salud, ciencias sociales, marketing, biología, ecología. La cobertura efectiva de 3.6 era del 16% de lo declarado. Esta inconsistencia entre el claim público y la validación se detectó al arrancar 3.6.b y se corrigió con dos enmiendas.

**Enmiendas aprobadas**:

- **D10** — Añadir tres datasets no-bancarios icónicos al alcance de 3.6:
  - **Breast Cancer WDBC** (UCI 17) — salud, binario, 30 features numéricas continuas, 569 filas. Contrasta con German Credit (mixto) y Car Evaluation (categórico puro).
  - **Iris** (UCI 53) — biología, multiclase K=3 balanceado, 4 features numéricas continuas, 150 filas. Ejercita Hand & Till AUC en condiciones óptimas.
  - **Blood Transfusion** (UCI 176) — ciencias sociales / comportamiento, binario, marco RFM, 748 filas, 4 features numéricas con empates intensos.
  Cobertura resultante: 4 de los 6 dominios declarados (banca, salud, biología, ciencias sociales).

- **D11** — Diferir marketing y ecología a una sub-fase nueva, 3.6.e, recuperada del roadmap original (donde figuraba como "Modo no-bancario"). Motivo: no existen datasets icónicos y limpios en esos dominios que quepan en el budget de fixtures sin abrir decisiones de feature engineering fuera de alcance. Los candidatos razonables (Wholesale Customers para marketing, Abalone para ecología) tienen particularidades que requieren diseño propio.

**Hashes verificados**: durante esta sesión se descargaron y verificaron los seis archivos fuente desde `archive.ics.uci.edu`. Los SHA256 quedan documentados en `docs/3.6_design_public_datasets.md` §4.4 y se hardcodearán en `scripts/fetch_datasets.py` durante 3.6.b. Ninguna de las seis URLs legacy respondió con error.

**Impacto en el diseño**: el documento `docs/3.6_design_public_datasets.md` se enmienda in situ (no se reescribe): §0.1 actualizado a "seis datasets"; §2 ampliado con tres subsecciones nuevas (§2.4–§2.6) y la subsección de exclusión renumerada a §2.7 con el bullet de Iris eliminado; §3 ampliado con tres subsecciones de normalización (§3.5–§3.7) y §3.5 renumerada a §3.8; §4.4 nueva con los hashes verificados; §5.1 con el nuevo budget de fixtures (~270 KB); §8.2 con la cobertura ampliada de riesgo. El header declara ahora once decisiones (D1–D11).

**Regla de gobernanza observada**: la enmienda se documenta en el mismo bloque en que se decide, no se difiere. La regla "Phase closure documentation: never deferred" cubre también las ampliaciones de alcance de sub-fases en curso.

**Referencias**: docs/3.6_design_public_datasets.md §2.4–§2.7, §3.5–§3.7, §4.4, §5.1; docs/roadmap.md sub-fase 3.6.e; README.md (claim multi-dominio del 11/10/2026); docs/design_decisions.md §0.2 (perfil biologist/social scientist).

---

### 16/10/2026 — Fase 3.6.b: script de descarga y fixtures versionadas

**Estado**: ✅ Cerrada.

**Modelo**: Kimi K3 vía Moonshot AI directo (OpenCode 1.19.0).

**Revisor**: Marco Rengel.

**Alcance**: Creado `scripts/fetch_datasets.py` (descarga las 6 URLs legacy de UCI, verifica SHA256, normaliza y escribe los CSVs en `tests/fixtures/uci/`). Creadas las 6 fixtures versionadas:
- german_credit (1000 filas)
- car_evaluation (1728 filas)
- balance_scale (625 filas)
- breast_cancer_wdbc (569 filas)
- iris (150 filas)
- blood_transfusion (748 filas)

**Verificación**: El script escribió el CSV y un sidecar `.sha256` por cada dataset. La descarga verificó los hashes contra los valores hardcoded. Suite 416/416 intacta.

---

### 16/10/2026 — Fase 3.6.c y 3.6.d: tests de integración y cierre

**Estado**: ✅ Cerrada. Fase 3.6 completa.

**Alcance**: Creado `tests/test_uci_integration.py` (6 tests que anclan los fingerprints exactos de los 6 datasets). Creado `docs/validation_results_3.6.md` con las métricas cuantitativas y comparación cualitativa con la literatura. Suite sube a 422/422.

**Verificación**: Los 6 tests de integración pasan en verde.

---

### 17/10/2026 — Auditoría cruzada, corrección terminológica y limpieza documental

**Estado**: Cerrada. Documentación sincronizada con la realidad del repositorio. Sin cambios de código; suite 422/422 intacta.

**Modelo**: Gemini y Copilot (auditoría cruzada); edición manual en VS Code (aplicación de correcciones).

**Revisor**: Marco Rengel.

**Artefactos**: docs/design_decisions.md, docs/methodology.md, docs/philosophy.md, docs/philosophy.es.md, docs/estado_proyecto.md, docs/api.md, README.md, README.es.md.

**Contexto**: Sesión de auditoría documental previa a la reanudación de los pendientes de la Fase 3.7. Se revisaron de forma cruzada los documentos estructurales del repositorio con dos asistentes externos (Gemini y Copilot) para detectar desajustes entre lo declarado y lo implementado. El objetivo era triple: (a) alinear la terminología con la preparación del modo no-bancario (Fase 3.6.e), (b) eliminar datos personales del dossier técnico, (c) cerrar las zonas grises matemáticas que quedaban en methodology.md y design_decisions.md.

**Cambios aplicados**:

1. Terminología. Se unificó el vocabulario hacia "Modo Regulatorio" (o "Regulatory mode") en la documentación externa, manteniendo `GovernanceMode.BANKING` como nombre del Enum de Python por compatibilidad histórica y de fingerprint. La aclaración se recoge en docs/design_decisions.md §0.3 y §10.2 (nota de terminología), en docs/api.md, y en docs/philosophy.md / docs/philosophy.es.md. El objetivo: que un lector externo no asocie la herramienta exclusivamente a banca, preparando el terreno para el modo no-bancario de la Fase 3.6.e, sin romper la cadena de compatibilidad de los fingerprints ya emitidos.

2. Limpieza de datos personales en estado_proyecto.md. Se eliminaron referencias que no aportaban al dossier técnico y que comprometían la privacidad. El documento queda como dossier introductorio para un auditor/validador MRM, sin información personal innecesaria.

3. Asimetría del KS. Se documentó formalmente la limitación del KS por pares en el path multiclase: el estadístico se calcula de forma unidireccional sobre la coordenada p_i para i < j (no simetrizado), a diferencia del AUC de Hand & Till que sí promedia ambas direcciones. La limitación está registrada en docs/design_decisions.md §7.7 ("Unidirectional pairwise KS in multiclass (deferred to Phase 3.7)") y en docs/methodology.md §8.11 ("Fidelity note on pairwise KS"), con la tarea 3.7.b como resolución programada (promediar KS_ij y KS_ji) antes de la v1.0.0 estable.

4. PD Floor. Se documentó formalmente el comportamiento del suelo regulatorio en el path multiclase: la implementación aplica pd_temp[c] = max(pd_floor, pd_jeffreys[c]) componente a componente y renormaliza (pd_final = pd_temp / sum(pd_temp)), lo que produce un "soft floor" en lugar de un floor estricto por componente. La nota de que esta renormalización se aplica también para K=2 (con desviación numéricamente despreciable del floor estricto) quedó registrada explícitamente en docs/methodology.md §6.6. La justificación de diseño (soft floor simétrico y neutral para K≥2) está en docs/design_decisions.md §6.4 y en el diseño de la Fase 3.1.

**Hallazgos**:

- La auditoría cruzada con dos asistentes externos confirmó que la terminología "BANKING" en código y "Regulatory mode" en documentación era una fuente de fricción para un lector externo que no conociera el histórico del proyecto. La distinción quedó explícita en los cuatro sitios donde aparece.
- El KS por pares asimétrico había sido detectado durante el diseño de la Fase 3.5 (decisión D4) pero no estaba formalmente documentado como limitación matemática con cita explícita a la tarea 3.7.b. La entrada actual lo cierra.
- El PD Floor multiclase había quedado descrito de forma ambigua entre design_decisions.md y methodology.md (el diseño original asumía floor estricto; la implementación aplica soft-floor renormalizado). La entrada actual documenta el comportamiento real del código y elimina la ambigüedad.

**Nota de gobernanza**: Esta sesión detectó un fallo de proceso: la auditoría del 17/10 no generó entrada en audit_log.md en su momento, aunque sí se reflejó en los documentos de contexto. La regla "Phase closure documentation: never deferred" cubre las sub-fases de código pero no explícitamente las sesiones de auditoría documental. Esta entrada cierra el hueco. Se refuerza la práctica: toda sesión que modifique documentación estructural del proyecto debe generar su entrada en audit_log.md en el mismo bloque.

**Decisión PyPI (regla 12/10/2026)**: Los cambios en README.md y README.es.md dejan la página pública de PyPI (1.0.0a6) desincronizada hasta la próxima release. Decisión documentada: opción (b), esperar a la próxima release con cambios de código. No se publica 1.0.0a7 solo por cosmética. Si el autor decide lo contrario, el procedimiento es: bump de versión en pyproject.toml y frontend_v3/__init__.py, actualización de READMEs, build, twine check, twine upload, verificación en venv aislado. Sin decisión explícita, la sub-fase no se considera cerrada (regla del 12/10/2026).

**Tests**: 422/422 PASSED (sin cambios de código; solo documentación).

**Referencias**:
- docs/philosophy.md y docs/philosophy.es.md (terminología).
- docs/design_decisions.md §0.3, §6.4, §7.7, §10.2.
- docs/methodology.md §6.6, §8.11.
- docs/estado_proyecto.md (limpieza de datos personales).
- docs/api.md (nota de terminología en GovernanceMode).
- docs/audit_log.md entradas del 15/10/2026 (Fase 3.5) y 16/10/2026 (cierre de cosméticos + Fase 3.6).

---

### 18/10/2026 — Cierre del bloque cosmético de READMEs y philosophy

**Estado**: Cerrada. Commit 7334f65. Suite 422/422 PASSED intacta.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=high (documentación pura; política AGENTS.md).

**Revisor**: Marco Rengel.

**Contexto**: cierre de los tres pendientes inmediatos detectados en el móvil el 17/10/2026. Documentación pura: cero cambios en backend_v3/ ni frontend_v3/; cero cambios en tests; cero cambios de API.

**Artefactos**:
- README.md (2 líneas modificadas).
- README.es.md (5 líneas modificadas).
- docs/philosophy.md (2 líneas modificadas).

**Cambios aplicados**:

1. README.md — Resumen ejecutivo: se restauró la mención "CHAID (classic and Exhaustive)" en la frase del resumen. La mención se había perdido al reescribir el párrafo. Coincide ahora con la tabla de capacidades, que ya usaba "CHAID classic and Exhaustive".

2. README.md — Sección Philosophy: las comillas rectas dobles de la frase central se sustituyeron por comillas tipográficas curvas U+201C (LEFT DOUBLE QUOTATION MARK) y U+201D (RIGHT DOUBLE QUOTATION MARK). Coherencia estética con philosophy.md y philosophy.es.md. El texto interno de la cita no cambió.

3. README.es.md — Resumen ejecutivo: se restauró "CHAID (clásico y Exhaustive)" en la frase equivalente. "Exhaustive" se mantiene en inglés por ser el nombre propio de la variante y por coherencia con la tabla de capacidades.

4. README.es.md — Sección "¿Por qué TreeGov?": eliminación del texto bilingüe remanente. Título pasa de "## ¿Por qué TreeGov? / Why TreeGov?" a "## ¿Por qué TreeGov?". Encabezados de tabla pasan de "| Si necesita... / If you need... | Utilice... / Use... |" a "| Si necesita... | Utilice... |". Descripciones de fila pasan de "Deep Learning" a "Aprendizaje profundo" y de "Gradient Boosting" a "Potenciación del gradiente". Nombres de herramienta (PyTorch, TensorFlow, XGBoost, LightGBM, scikit-learn) se mantienen por ser nombres propios.

5. docs/philosophy.md — Título: "## Why TreeGov exists" pasa a "## Why does TreeGov exist?" (gramática correcta). Sección "The core sentence": comillas rectas sustituidas por tipográficas U+201C/U+201D, igual que en README.md.

**Hallazgos y notas de gobernanza**:

- Verificación UTF-8. El diff mostrado por PowerShell aparecía con mojibake por un problema ya documentado (audit_log 05/10/2026, AGENTS.md): la consola decodifica con codepage no UTF-8 y corrompe la salida, aunque el archivo en disco esté correcto. La tubería "git diff | Out-File -Encoding utf8" NO arregla el problema, porque la corrupción ocurre antes. Verificación fiable: script Python que lee los archivos con io.open(encoding="utf-8") y comprueba contenido y puntos de código (U+201C/U+201D). Alternativa más limpia para futuros diffs: "git diff --output=archivo.txt" (escribe bytes directamente, sin pasar por la tubería de strings de PowerShell). Esta lección queda reforzada en AGENTS.md sección Entorno.

- Regla PyPI (12/10/2026). El README en PyPI está congelado en 1.0.0a6. El bloque actual modifica README.md y README.es.md. Decisión explícita (opción b, recomendada): esperar a la próxima release con cambios de código. No se publica 1.0.0a7 solo por cosmética. Si el autor decide lo contrario, el procedimiento es: bump de versión en pyproject.toml y frontend_v3/__init__.py, actualización de READMEs, build, twine check, twine upload, verificación en venv aislado. Sin decisión explícita, la sub-fase no se considera cerrada (regla del 12/10/2026).

**Tests**: 422/422 PASSED. Cero regresiones.

**Referencias**:
- Commit 7334f65.
- docs/audit_log.md entrada del 17/10/2026 (auditoría cruzada).
- AGENTS.md sección Entorno (UTF-8 en PowerShell).
- docs/roadmap.md sección "Recorded architectural decisions" (regla PyPI).

---

### 18/10/2026 — Fase 3.7.b: Simetrización del KS por pares en multiclase

**Estado**: ✅ Cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=max (política AGENTS.md: cambio de lógica numérica y multi-archivo).

**Revisor**: Marco Rengel.

**Contexto**: El diseño de la Fase 3.5 (decisión D4) estableció el uso del mínimo de los KS por pares como worst-case para K > 2. Sin embargo, la implementación evaluaba el estadístico de forma unidireccional (usando solo la columna `p_i`), rompiendo la simetría con el AUC de Hand & Till, que sí promedia ambas direcciones. Esta asimetría quedó documentada en `design_decisions.md` §7.7 y se programó su resolución para la Fase 3.7.b.

**Cambios aplicados**:
- `backend_v3/validation.py`: en el bucle de cálculo multiclase, se captura el retorno de `ks` en la dirección inversa (`ks_ji`) y se promedia con el directo (`ks_ij`) antes de guardarlo en `ks_pairs`.
- `tests/test_validation.py`: actualizado `test_multiclass_k3_worst_case_ks` para reflejar el nuevo valor simetrizado (0.75 en lugar de 1.0) del par (0,2). El peor caso (`min`) se mantiene en 0.5.
- `docs/methodology.md` §8.11: actualizada la fórmula del KS para reflejar el promedio de ambas direcciones. Eliminado el párrafo de "Fidelity note" que documentaba la asimetría.
- `docs/design_decisions.md` §7.7: actualizada la sección para reflejar la resolución del diferido.

**Hallazgos**:
- La simetrización altera numéricamente el payload de `ks_pairs` para K > 2, pero mantiene el invariante K=2 bit a bit (las dos direcciones son idénticas cuando `p_1 = 1 - p_0`).
- No hay impacto en `Session` ni en la GUI, ya que el DTO consume los pares ya calculados.

**Tests**: 422/422 PASSED. Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §7.7
- `docs/methodology.md` §8.11
- `docs/3.5_design_multiclass_weighted_reports.md` (decisión D4)

---

### 18/10/2026 — Fase 3.7.c: Exposición pública de min_child_weight

**Estado**: ✅ Cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=max (política AGENTS.md: cambio de firma pública, multi-archivo, contrato del wizard).

**Revisor**: Marco Rengel.

**Contexto**: la Fase 3.2.e introdujo `min_child_weight` como parámetro keyword-only de `TreeBuilder`, pero quedó fuera de la firma pública de `Session.train` y del asistente gráfico. La Fase 3.7.c cierra esa brecha: expone el parámetro en la API pública y en el paso 4 del wizard.

**Cambios aplicados**:
- `backend_v3/session_state.py`: `Session.train` gana `min_child_weight: float | None = None` (keyword-only); se propaga a `TreeBuilder`; el event log registra el valor cuando está activo.
- `frontend_v3/wizard.py`: `GovernancePage` gana un `QDoubleSpinBox` con etiqueta y hint; `current_config()` expone `"min_child_weight"`; la convención es 0.0 = desactivado → `None` en el cfg.
- `frontend_v3/main_window.py`: `_train_pipeline` propaga `cfg["min_child_weight"]` a `Session.train` (fail-fast, mismo patrón que `target_class` y `weight_col`).
- `frontend_v3/i18n.py`: dos claves nuevas × dos idiomas (`step4_min_child_weight`, `step4_min_child_weight_hint`).
- `tests/test_e2e_mainwindow.py` (2 dicts), `tests/test_e2e_reports.py` (1 dict), `tests/test_tree_view.py` (1 dict) y `tests/test_wizard.py` (1 dict + actualización del conjunto esperado de claves en `test_wizard_finish_emits_config`): añadida la clave `"min_child_weight": None` a los cinco cfg manuales, más el assert de contrato del wizard.
- `docs/api.md`: firma pública actualizada.
- `docs/design_decisions.md` §13.5: nota de actualización.

**Invariantes**:
- El default `None` preserva la paridad bit a bit con el comportamiento pre-3.2 (el fingerprint no cambia si el parámetro no se activa; los `TreeNode` y las métricas son idénticos).
- Solo tiene efecto numérico cuando la sesión es ponderada (`weight_col` declarado). Sin pesos, la comprobación actúa sobre un vector de unos y resulta redundante con `min_child_size`; el hint del wizard lo advierte explícitamente.
- El fingerprint ya incluía `"min_child_weight"` desde la Fase 3.2.e; no hay cambio en el contrato del fingerprint, solo en cómo se declara el valor.

**Hallazgos**:
- El fail-fast de `_train_pipeline` (sin `.get()` con defaults) obliga a actualizar todos los cfg manuales de los tests E2E en el mismo bloque. La iteración automática localizó y actualizó cuatro archivos (`test_e2e_mainwindow.py`, `test_e2e_reports.py`, `test_tree_view.py`, `test_wizard.py`), con cinco diccionarios en total, más el assert de conjunto exacto de claves del contrato del wizard en `test_wizard_finish_emits_config`.
- El comportamiento con `min_child_weight` activo pero `weight_col=None` no se bloquea en el wizard (el analista puede activarlo sin declarar pesos). El hint lo advierte, pero es una decisión de diseño diferible: si en la Fase 3.7.a o posterior se decide endurecerlo, se puede añadir una validación cruzada en `Session.train`.

**Tests**: 422/422 PASSED. Cero regresiones.

**Referencias**:
- `docs/design_decisions.md` §13.5
- `docs/api.md`
- `docs/audit_log.md` entrada del 10/10/2026 (Fase 3.2.e)
- `docs/roadmap.md` (fase 3.7.c)

---

### 18/10/2026 — Fase 3.7.a: Auditoría de seguridad y privacidad

**Estado**: ✅ Cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=max (política AGENTS.md: cambio multi-archivo, requisito de release).

**Revisor**: Marco Rengel.

**Contexto**: la Fase 3.7.a del roadmap exigía una auditoría de seguridad antes de la v1.0.0. El hallazgo H6 de la sesión de GUI (13/10/2026) ya había señalado que los logs DEBUG y los reports HTML contienen información sensible. Esta sub-fase formaliza el modelo de amenazas, la política de retención y las advertencias en la GUI.

**Cambios aplicados**:
- `docs/security_audit.md` (nuevo): documento formal que define el modelo de amenazas, la política de retención de logs, la sensibilidad de los reports HTML y la justificación de los avisos en la GUI.
- `frontend_v3/i18n.py`: dos claves nuevas × dos idiomas (`security_warning_title`, `security_warning_body`).
- `frontend_v3/main_window.py`: añadida la bandera `_security_warning_shown`. En `_load_dataset_path`, se muestra un `QMessageBox.warning` la primera vez que se carga un dataset en la sesión (suprimido bajo offscreen para no colgar el CI). El evento se registra en el log.

**Tests**: 430/430 PASSED. Cero regresiones (el aviso está suprimido en el entorno offscreen, por lo que los tests E2E no se ven afectados).

**Referencias**:
- `docs/roadmap.md` (fase 3.7.a)
- `docs/security_audit.md`
- `docs/philosophy.md` §"Development vs end use"
- `docs/audit_log.md` entrada del 13/10/2026 (hallazgo H6)

---

### 18/10/2026 — Fase 3.7.d: tests UCI con CHAID y QUEST (entrada retroactiva)

**Estado**: ✅ Cerrada (entrada retroactiva; el código se cerró en el commit `c72df69` pero nunca se documentó en este archivo).

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3.

**Revisor**: Marco Rengel.

**Contexto**: la sub-fase 3.7.d ampliaba `tests/test_uci_integration.py` más allá del motor C&RT. El trabajo se completó y commiteó (`c72df69`) pero su entrada de cierre en `docs/audit_log.md` se omitió, violando la regla "Phase closure documentation: never deferred". Esta entrada cierra el hueco en retrospectiva.

**Cambios aplicados** (ya presentes en el repositorio desde `c72df69`):
- `tests/test_uci_integration.py`: `_build_session` y `_check_dataset` refactorizados para aceptar el motor (`engine="CRT"` por defecto). Diccionarios nuevos `EXPECTED_CHAID` y `EXPECTED_QUEST` con fingerprints y conteos de nodos reales capturados de los AssertionError.
- 8 tests nuevos: 2 con CHAID (Car Evaluation, Balance Scale) y 6 con QUEST (German Credit, Car Evaluation, Balance Scale, Breast Cancer WDBC, Iris, Blood Transfusion).

**Tests**: la suite pasó de 422/422 a 430/430 PASSED. Cero regresiones.

**Nota de gobernanza**: la omisión original de esta entrada violó la regla "Phase closure documentation: never deferred" (ver `docs/roadmap.md` sección "Recorded architectural decisions"). Se detectó durante el cierre formal de la Fase 3.7 y se documenta aquí en el mismo bloque.

**Referencias**:
- Commit `c72df69`.
- `docs/roadmap.md` (fase 3.7.d).
- `docs/audit_log.md` entrada del 16/10/2026 (Fases 3.6.c/d, donde se creó `tests/test_uci_integration.py` con los 6 tests C&RT originales).

---

### 18/10/2026 — Cierre formal de la Fase 3.7

**Estado**: ✅ Fase 3.7 cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3.

**Revisor**: Marco Rengel.

**Recuento de sub-fases**:
- **3.7.a** — Auditoría de seguridad y privacidad: `docs/security_audit.md` (modelo de amenazas, retención de logs, sensibilidad de reports HTML) + `QMessageBox` de aviso en la primera carga de dataset por sesión (`frontend_v3/main_window.py`, claves i18n `security_warning_title`/`security_warning_body`). Cerrada el 18/10/2026.
- **3.7.b** — Simetrización del KS por pares en multiclase (`backend_v3/validation.py`). Cerrada el 18/10/2026.
- **3.7.c** — Exposición pública de `min_child_weight` en `Session.train` y wizard. Cerrada el 18/10/2026.
- **3.7.d** — Ampliación de tests UCI con CHAID y QUEST (8 tests nuevos). Cerrada en código el 18/10/2026 (commit `c72df69`); entrada retroactiva en este mismo bloque.
- **3.7.e** — Correcciones pre-release tras auditoría externa (H1, H2, pd_floor K=2). Ver la entrada siguiente de este mismo bloque.

**Alcance**: la Fase 3.6.e (modo no bancario) queda fuera del alcance de la v1.0.0; se planifica para la v1.1.0 o posterior.

**Tests**: 431/431 PASSED.

**Próximo paso**: bump a 1.0.0rc1 y publicación en PyPI.

**Referencias**:
- `docs/roadmap.md` (Fase 3.7).
- Las entradas del 18/10/2026 de este archivo (3.7.a, 3.7.b, 3.7.c, 3.7.d retroactiva, 3.7.e).

---

### 18/10/2026 — Fase 3.7.e: correcciones pre-release

**Estado**: ✅ Cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=max (política AGENTS.md: corrección de bugs y multi-archivo).

**Revisor**: Marco Rengel.

**Contexto**: tres fixes aplicados tras recibir una auditoría externa independiente (Gemini Argon MAX y Copilot Think Deeper, con el mismo prompt). Dos fixes provienen de los hallazgos H1 y H2 de la sesión de GUI del 13/10/2026; el tercero es un bug numérico del floor de PD en K=2 detectado por la auditoría externa.

**Cambios aplicados**:

(a) **H1 — radio buttons del wizard invisibles.** Fix en `frontend_v3/resources/styles.qss` con reglas `QRadioButton::indicator::checked` y `QRadioButton::indicator:hover`. Verificado con los tests E2E del wizard.

(b) **H2 — target por defecto era la primera columna del CSV.** Fix en `frontend_v3/wizard.py`: el combo `_combo_target` de `PredictorsPage` arranca con un placeholder explícito (`currentData() == None`) y `isComplete()` exige target elegido. Clave i18n nueva `step2_target_placeholder` en EN/ES. Tres tests adaptados en `tests/test_wizard.py` (`test_wizard_navigation`, `test_wizard_predictors_validation`, `test_wizard_finish_emits_config`) más el helper nuevo `_select_target`.

(c) **pd_floor en K=2.** La renormalización suave podía dejar `pd_final[0] < pd_floor`, violando BCBS CRE 20.39 (cota dura). Fix en `backend_v3/tree_builder.py`, rama `K == 2`: asignar `1 - pd_final[0]` directamente sin renormalizar. Test nuevo `test_pd_floor_hard_bound_binary` en `tests/test_tree_builder.py`, verificado numéricamente (fixture de 100 filas con hojas puras: `pd_jeffreys[0] = 0.5/51 ≈ 0.0098 < 0.01`; con la renormalización suave `pd_final[0]` quedaba en 0.009998; con el floor duro es ≥ 0.01 y la suma es 1.0 con tolerancia 1e-12).

**Tests**: 431/431 PASSED. Cero regresiones.

**Referencias**:
- `docs/audit_log.md` entrada del 13/10/2026 (hallazgos H1 y H2).
- `docs/methodology.md` §6.6 (PD floor).
- `docs/design_decisions.md` §6.4 (justificación del floor).
- BCBS CRE 20.39 (cota dura del floor de PD).

---

### 18/10/2026 — Publicación de v1.0.0rc1 en PyPI y actualización visual de READMEs

**Estado**: ✅ Cerrada.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3.

**Revisor**: Marco Rengel.

**Resumen**: publicada la Release Candidate v1.0.0rc1 en PyPI, incluyendo la corrección del PD_Floor en K=2 (cota dura BCBS CRE 20.39, ver entrada 3.7.e). Además, se añadieron gráficos de arquitectura Mermaid a los READMEs: bloque en español en `README.es.md` (commit `9bc4886`) y su versión en inglés en `README.md` (corregida en commit `71dbd27` tras detectar que el primer insert quedó en español).

**Tests**: 431/431 PASSED.

**Referencias**:
- `docs/audit_log.md` entrada del 18/10/2026 (Fase 3.7.e).
- `README.md`, `README.es.md` (sección Philosophy/Filosofía).

---

### 19/10/2026 — Cierre de deuda documental y registro de la poda en el roadmap

**Estado**: Cerrada. Sin cambios de código. Suite 431/431 PASSED.

**Motivación**:
Detectados huecos documentales menores y falta de registro formal de la deuda de poda durante la sesión de inicio de la deuda post-rc1. Se aplica el checklist de cierre ampliado a 6 documentos definido el 12/10/2026.

**Cambios aplicados**:
- `docs/roadmap.md`: añadida subsección "Cost-complexity pruning (poda) integration" en la sección Deferred, con prioridad Alta para 1.0.0 estable.
- `docs/contexto_para_nueva_sesion.md`: actualizada la versión publicada a 1.0.0rc1 y añadida la deuda de la poda a la lista de deudas diferidas.
- `docs/estado_proyecto.md`: sin modificación. Verificada la deuda de poda ya presente en los pendientes estructurales (introducida en el commit `eb17b2f` del 18/10); Kimi detectó que el cambio ya estaba y el revisor confirmó no duplicarlo.
- `docs/api.md`: añadida nota aclaratoria en `backend_v3.pruning` indicando que es API-only.
- `README.md` y `README.es.md`: actualizada la fila de poda para reflejar que es API-only, no cableada, y que usa conteos sin ponderar.
- `docs/audit_log.md`: esta misma entrada.

**Tests**: 431/431 PASSED (sin cambios de código).

**Referencias**: brief del 19/10/2026; regla del 16/10/2026 en `docs/roadmap.md`.

---

### 19/10/2026 (tarde) — Corrección de la atribución regulatoria del PD floor (BCBS CRE 32.4)

**Estado**: ✅ Cerrada. Suite 434/434 PASSED.

**Modelo**: OpenCode 1.19.0 + moonshotai/kimi-k3, reasoning=max
(cambio transversal multi-archivo, cambio de firma pública de defaults,
regeneración de artefacto MRM).

**Revisor**: Marco Rengel.

**Motivación**:

Durante la sesión de inicio de la deuda post-rc1 se detectó, a partir de
una auditoría externa (Copilot, con verificación contra el Basel Framework
consolidado publicado por BIS), que la atribución regulatoria del piso de
PD era **materialmente incorrecta en dos dimensiones**:

1. **Referencia normativa**: el proyecto atribuía el floor de PD a
   "BCBS CRE 20.39". Ese apartado regula *covered bonds* del enfoque
   estándar, no el floor de PD del enfoque IRB. El floor vive en
   **CRE 32.4**.
2. **Valor**: el proyecto usaba 0.03% (3 bps). Ese es el floor de
   **Basel II**. La reforma final de Basel III (diciembre 2017,
   efectiva 2023) lo subió a **0.05%** (5 bps) para corporativos,
   bancos y retail, con excepción soberana (0.03% o exención, según
   jurisdicción).

El proyecto se declara MRM. Una atribución regulatoria incorrecta no es
una "desviación documentada"; es un hallazgo material. Se corrige.

**Auditoría documental adicional detectada durante el bloque**:

El mismo patrón de sobre-atribución normativa apareció en `stability.py`:
los umbrales 0.10/0.25 del PSI/CSI se atribuían a "Basel/EBA", cuando son
convención de la industria (Siddiqi 2006) y no prescripción regulatoria.
Se corrige en el mismo bloque (decisión ZG-8 del revisor).

**Decisiones del revisor**:

- **(A) Opción A**: `pd_floor` default universal 0.0005 en modo BANKING,
  con disclaimer explícito de que la excepción soberana (0.03%) no está
  modelada y debe pasarse `pd_floor=0.0003` explícitamente.
- **Regenerar y anotar** `docs/validation_results_3.6.md`: el informe se
  regenera con el nuevo default, se añade una sección "Revision notes"
  que explica el cambio, y el histórico anterior vive en el git log.
- **Reconocer el error** en esta misma entrada, con esas palabras.
- **Publicar `1.0.0rc2`**: la corrección es significativa (atribución
  normativa + default regulatorio) y merece una nueva release candidate.

**Cambios aplicados (3.8.a — backend)**:

- `backend_v3/tree_builder.py`: default `pd_floor` 0.0003 → 0.0005;
  docstrings y comentario con "BCBS CRE 20.39" → "BCBS CRE 32.4".
- `backend_v3/session_state.py`: idem en `Session.train`.
- `backend_v3/types.py`: docstring de `GovernanceMode.BANKING`.
- `backend_v3/stability.py`: elimina "Basel/EBA" de docstrings de
  `traffic_light()` y del módulo; el origen de los umbrales se atribuye
  a Siddiqi (2006), y se añade negación explícita ("no prescrito por
  Basilea ni EBA"). Umbrales numéricos (0.10, 0.25, 0.20, 0.40) intactos.

**Cambios aplicados (3.8.b — frontend)**:

- `frontend_v3/i18n.py`: `step4_govmode_banking_desc` (EN y ES) y
  `tree_prop_floor_note` (EN y ES) reformulados con "PD Floor 0.0005
  (BCBS CRE 32.4)" y "PD floor binding (BCBS CRE 32.4)".
- `frontend_v3/i18n.py`: **bug preexistente corregido** — clave
  `step2_target_placeholder` estaba duplicada en cada bloque (`en` y `es`),
  de modo que el usuario en inglés veía el placeholder en español (la
  segunda asignación gana en Python). Se conserva una única línea por
  bloque con el texto correcto de su idioma.
- `frontend_v3/wizard.py`: `_spin_floor.setValue(0.0003)` → `0.0005` en
  `GovernancePage.__init__` y `_sync_governance_controls`.

**Cambios aplicados (3.8.c — script + informe)**:

- `scripts/validate_uci.py`:
  - Sustituye `ENGINE_MATRIX` (heurística) por `VALID_ENGINES` (dict
    explícito de pares dataset → motores). La cobertura es ahora de
    **14 pares** (6 CRT + 2 CHAID + 6 QUEST), alineada con
    `tests/test_uci_integration.py`.
  - `_run_one` retorna `dict` con los campos del informe (o `{'error': ...}`).
  - `run()` imprime a stdout y, si no hay errores, llama a
    `_write_markdown(results)` para escribir
    `docs/validation_results_3.6.md`.
  - `_write_markdown` genera el md completo (tabla + Qualitative
    Literature Comparison + Revision notes) desde constantes del
    script. El md es reproducible bit-a-bit dado el código del
    repositorio; la fecha y el commit que lo produjeron se consultan
    con `git log -- docs/validation_results_3.6.md`.
  - Nota de revisión corregida: la primera iteración decía "smallest
    empirical leaf PD is approximately 0.043 for Iris" — error del
    revisor, no del agente. La cifra real y el dataset con el mínimo
    teórico son **0.96% para Car Evaluation** (K=4, min_child_size=50),
    ~19× por encima del floor 0.05%.
- `docs/validation_results_3.6.md` regenerado: 14 filas
  (dataset, motor), fingerprints nuevos, sección "Revision notes"
  con la motivación y el impacto.

**Cambios aplicados (3.8.d — tests)**:

- `tests/test_tree_builder.py::test_governance_banking_default`:
  asertos actualizados a `0.0005` (valor y `max(...)`); docstring.
- `tests/test_wizard.py::test_wizard_finish_emits_config`:
  `assert cfg["pd_floor"] == 0.0005`.
- `tests/test_wizard.py::test_mainwindow_wizard_config_trains`:
  `cfg` manual con `"pd_floor": 0.0005`.
- `tests/test_uci_integration.py`: los 14 fingerprints
  (`EXPECTED`, `EXPECTED_CHAID`, `EXPECTED_QUEST`) recapturados.
  Verificación cruzada uno a uno contra la tabla del md: 14/14
  coinciden en fingerprint y en `nodes`.
- `tests/test_e2e_mainwindow.py` (2 cfg), `tests/test_e2e_reports.py`
  (1 cfg), `tests/test_tree_view.py` (1 cfg): `"pd_floor": 0.0005`
  por consistencia con el nuevo default del wizard. No cambian
  el conteo de tests, no cambian la lógica de los E2E.

**Cambios aplicados (3.8.e — tests nuevos)**:

- `tests/test_tree_builder.py::test_pd_floor_hard_bound_binary_default`:
  verifica que con el default 0.0005, una hoja con
  `pd_jeffreys[0] < 0.0005` recibe `pd_final[0] == 0.0005` exacto
  (hard bound).
- `tests/test_tree_builder.py::test_fingerprint_banking_default_vs_legacy_floor`:
  verifica que el fingerprint distingue el default (0.0005) del
  valor legacy de Basel II (0.0003).
- `tests/test_wizard.py::test_wizard_default_pd_floor_spinbox`:
  verifica que el spin box del Step 4 arranca en 0.0005 y que
  `_sync_governance_controls` restaura 0.0005 al volver de RESEARCH
  a BANKING.

**Cambios aplicados (3.8.f — documentación + versión)**:

- `docs/methodology.md`: §6.3, §6.4, §6.5, §6.6, §8.5 y referencias
  regulatorias actualizadas (CRE 32.4; K=2 hard floor vs K>2 soft floor;
  Siddiqi 2006).
- `docs/api.md`: firma pública de `Session.train` con `pd_floor=0.0005`.
- `docs/philosophy.md`, `docs/philosophy.es.md`, `docs/3.1_design_multiclass.md`,
  `.treegovrules`, `docs/roadmap.md`, `docs/estado_proyecto.md`,
  `docs/contexto_para_nueva_sesion.md`, `docs/prompt_para_asistente.md`,
  `README.md`, `README.es.md`: alineados con la referencia correcta.
- `pyproject.toml`, `frontend_v3/__init__.py`: bump a `1.0.0rc2`.

**Invariante preservado**:

- Las métricas numéricas reportadas en `docs/validation_results_3.6.md`
  (Gini, KS, AUC, Accuracy) **no cambian**, porque el floor no se
  activa en ningún dataset UCI bajo el `min_child_size` configurado.
  Solo cambian los fingerprints, porque `pd_floor` entra en el
  payload del `params_fingerprint`. Esto es exactamente lo que se
  espera de un cambio de gobernanza sin cambio de comportamiento
  numérico en la línea base publicada.
- C1 de la Fase 3.2 (sin pesos → idéntico al pre-3.2) sigue vigente;
  el cambio de `pd_floor` es ortogonal a la ponderación.

**Zonas grises detectadas por el agente durante el bloque y resueltas**:

- Contradicción funcional del wizard: el spin nativo pasaba `0.0003`
  mientras la etiqueta anunciaba `0.0005` y el backend ya era `0.0005`.
  Detectado por el agente antes de que se materializase en un bug de
  usuario; resuelto en 3.8.b.
- El `**Commit:** <HEAD>` embebido en el md apuntaba al commit padre
  (con `pd_floor=0.0003`), no al commit que contiene el md. Resuelto
  eliminando los campos `Generated:`/`Commit:`/`Python:` del md y
  delegando la trazabilidad temporal a `git log`. Regla derivada:
  **nunca embeber en un artefacto generado el commit que lo va a
  contener** (autorreferencia imposible de estabilizar).
- `docs/methodology.md` §6.6 desactualizado desde la Fase 3.7.e: el
  texto afirmaba soft-floor renormalization en K=2, pero el código
  aplica hard floor desde el 18/10. Detectado al preparar 3.8.f.
  Corregido en el mismo bloque: §6.6 reformulado con el comportamiento
  real (hard floor K=2, soft floor K>2) y referencia a los dos tests
  que lo anclan (`test_pd_floor_hard_bound_binary` y
  `test_pd_floor_hard_bound_binary_default`).
- Ambigüedad en la instrucción de cierre de `contexto_para_nueva_sesion.md`
  (párrafo 3.7/3.6.e): detectada por el agente, confirmada por el revisor
  (opción 1: preservar histórico 3.7 y sustituir solo el "Próximo hito").

**Tests**: 434/434 PASSED (antes del bloque: 431/431; +3 tests nuevos
que anclan el comportamiento del nuevo default).

**Referencias cruzadas**:

- Basel Framework consolidado (BIS, CRE 20.39 — covered bonds; CRE 32.4
  — floor de PD IRB).
- Reforma final Basel III (diciembre 2017).
- `docs/audit_log.md` 18/10/2026 (Fase 3.7.e, corrección previa del
  hard floor en K=2, que citaba CRE 20.39 por la misma confusión).
- `docs/validation_results_3.6.md` §Revision notes.
- `docs/roadmap.md` sección "✅ Phase 3.8".

### 20/10/2026 — Mini-cierre: correcciones post-rc2, checklist de 8, protocolo PyPI, disciplina MRM y protocolo de mini-cierre

**Estado**: ✅ Cerrada. Sin cambios de código analítico. Suite 434/434 PASSED al cierre del bloque.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=high (documentación pura) para las correcciones de código; edición manual en VS Code para la redacción del protocolo de mini-cierre y del Protocolo de Redacción de Prompts (excepción documentada: creación inicial de bloques de gobernanza, ver CONVENTIONS.md).

**Revisor**: Marco Rengel.

**Contexto**: sesión de cierre documental tras la publicación de `1.0.0rc2` (19/10/2026). Se detectaron tres huecos post-cierre que exigían corrección inmediata: (a) la fila de la Fase 3.8 en los READMEs no se había actualizado; (b) los diagramas Mermaid de los READMEs tenían fechas y conteos desactualizados; (c) `design_decisions.md` no reflejaba el nuevo default de `pd_floor` ni la corrección regulatoria de la Fase 3.8. Adicionalmente, la sesión formalizó cuatro protocolos de gobernanza que ya operaban de facto, pero no estaban escritos como regla.

**Cambios aplicados**:

**1. Corrección cosmética de READMEs y Mermaid.**
- `README.md` / `README.es.md`: fila de la tabla de fases para 3.8 actualizada a "Completed" / "Completada"; diagramas Mermaid actualizados a "Phases 0 → 3.8 complete" / "Fases 0 → 3.8 completas", "v1.0.0rc2 published on PyPI" / "v1.0.0rc2 publicada en PyPI", "434 / 434 tests PASSED", "Oct 20, 2026" / "20 oct 2026".
- `docs/estado_proyecto.md`: fecha de actualización a 20/10/2026; bloque narrativo de la Fase 3.8 añadido (la versión previa solo tenía la entrada en `roadmap.md` y `audit_log.md`).
- `docs/design_decisions.md`: nueva §10.4 ("Default PD floor value and the sovereign exception (Phase 3.8)") con `pd_floor = 0.0005` y cita a BCBS CRE 32.4.
- `docs/methodology.md` §6.3: cita regulatoria corregida a CRE 32.4 y default `0.0005`.

**2. Expansión del checklist de cierre a 8 documentos (para evitar saltos de profundidad).**
El checklist pasa de 6 a 8 documentos. Los dos nuevos son:
- `docs/api.md` (superficie pública de la API).
- `docs/design_decisions.md` (nueva entrada si el cambio introdujo un nuevo default o alteró un contrato de API).
Motivo: los tres huecos detectados en este cierre (fila del README, bloque narrativo en `estado_proyecto.md`, entrada en `design_decisions.md`) caen todos dentro del checklist ampliado. Con 8 entradas, el cierre de la Fase 3.8 los habría detectado. El cambio se propaga a `AGENTS.md`, `docs/contexto_para_nueva_sesion.md`, `docs/prompt_para_asistente.md` y `.treegovrules`, todos en el mismo bloque.

**3. Protocolo de Sincronización PyPI.**
Regla registrada en `AGENTS.md`, `docs/contexto_para_nueva_sesion.md`, `docs/prompt_para_asistente.md` y `docs/roadmap.md` (sección "Deferred"):
- **Cambios materiales** (código, defaults, contratos, citas regulatorias): publicar nueva versión en PyPI inmediatamente.
- **Cambios cosméticos** (fechas en diagramas, typos, tablas de estado, narrativa): NO publicar nueva versión. Diferir a la próxima release material y documentar la desincronización en `docs/roadmap.md` (sección "Deferred").
Motivo: tras la publicación de `1.0.0rc2` el 19/10/2026, el README de PyPI queda congelado. Publicar una `1.0.0rc3` solo por cosmética habría inflado el historial de releases sin justificación. La regla evita esa inflación y hace explícita la decisión.

**4. Declaración de Disciplina MRM en el software.**
`docs/philosophy.md` y `docs/philosophy.es.md` ganan una sección "MRM Discipline in Software Development" / "Disciplina MRM en el Desarrollo de Software": TreeGov no solo implementa MRM, el software en sí mismo se construye bajo disciplina MRM (diseño antes del código, humano en el circuito, verificación adversarial, trazabilidad inmutable). Motivo: la filosofía del proyecto ya estaba escrita, pero la disciplina de desarrollo era implícita.

**5. Protocolo de Mini-Cierre.**
Nueva regla registrada en `.treegovrules`, `AGENTS.md` y `docs/prompt_para_asistente.md` (texto idéntico en los tres). Establece que toda corrección post-cierre, resolución de deuda diferida o actualización documental pura genera su propia entrada en `audit_log.md` con fecha, artefactos, hallazgos, estado de la suite y referencias cruzadas. Incluye cinco anti-patrones observados en sesiones recientes (saltarse la auditoría de diseño, asumir el estado de los documentos, proponer hallazgos sin revisar todos los documentos relevantes, verificación en una sola dirección, correcciones post-cierre sin entrada). Motivo: el cierre de la Fase 3.8 y su corrección del 20/10/2026 dejaron un hueco de trazabilidad que esta regla previene. Referencias cruzadas a `docs/roadmap.md` ("Phase closure documentation: never deferred") y a la entrada del 17/10/2026.

**6. Nota de actualización en `design_decisions.md` §13.7 (saneamiento).**
Se añade al final de §13.7 (sin modificar el cuerpo original del 10/10/2026) una nota fechada el 20/10/2026 que aclara que la Fase 3.5.b (15/10/2026) ya resolvió la asimetría de D13 para el path multiclase, y que la asimetría restante es exclusiva del path binario (K=2). La nota de "Deferred" del 10/10/2026 se mantiene en lo esencial. Motivo: el cuerpo de §13.7 estaba desincronizado con el cierre de la Fase 3.5.b; la nota restaura la consistencia sin reescribir el histórico.

**Hallazgos**:
- **Protocolo ausente para correcciones post-cierre.** El cierre de la Fase 3.8 (19/10/2026) omitió la fila del README, el bloque narrativo en `estado_proyecto.md` y la entrada en `design_decisions.md`. El bloque de corrección del 20/10/2026 los corrigió, pero no generó entrada propia en `audit_log.md`. Se adopta el **Protocolo de Mini-Cierre** (texto canónico en `.treegovrules`, `AGENTS.md` y `docs/prompt_para_asistente.md`) para prevenir el hueco en futuras sesiones.
- **Desincronización en `design_decisions.md` §13.7.** La decisión diferida D13 sigue sin nota de actualización en el cuerpo de §13.7, aunque la Fase 3.5.b (15/10/2026) ya resolvió la asimetría para el path multiclase. Se corrige en la nota de actualización del bloque 6.
- **Riesgo de "hallazgos sin evidencia" en sesiones de auditoría.** Durante la sesión de auditoría previa a este mini-cierre se emitieron cuatro hallazgos de gobernanza; dos resultaron falsos (D13 no estaba en `roadmap` "Deferred" ni los tags `a1`–`a6` tampoco, sino en `estado_proyecto.md` §10), uno quedó reducido a consistencia (§13.7 sin nota in-place), y uno se confirmó (ausencia de entrada en `audit_log` para el 20/10/2026). El anti-patrón 2 del Protocolo de Mini-Cierre ("asumir el estado de los documentos") lo previene.
- **Verificación en una sola dirección.** La sesión de auditoría reveló que el asistente estratégico también es falible y debe ser verificado contra el working tree, `git log` y los documentos. El anti-patrón 4 del Protocolo de Mini-Cierre lo codifica.

**Tests**: 434/434 PASSED (sin cambios de código en este bloque; solo documentación).

**Referencias**:
- Commit `dd5e95e` (`docs: deep synchronization pass and PyPI protocol enforcement`), visible tip del bloque.
- `docs/audit_log.md` entrada del 19/10/2026 (tarde) — cierre de la Fase 3.8.
- `docs/roadmap.md` sección "Recorded architectural decisions" — regla "Phase closure documentation: never deferred".
- `AGENTS.md` sección "Documentación obligatoria" — checklist de 8 documentos, Protocolo PyPI y Protocolo de Mini-Cierre.
- `docs/prompt_para_asistente.md` Sección 11 — Protocolo de Redacción de Prompts.
- `docs/philosophy.md` / `docs/philosophy.es.md` — Disciplina MRM en el Desarrollo de Software.
- `docs/design_decisions.md` §13.7 — nota de actualización del 20/10/2026.

### 20/10/2026 — Resolución de D13 (ponderación de métricas en Gains Table binaria)

**Estado**: ✅ Cerrada. Suite 435/435 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=max.

**Revisor**: Marco Rengel.

**Contexto**: Cierre de la deuda técnica D13, que dejaba las métricas de cabecera (KS/AUC/Gini) de la gains table binaria sin ponderar, creando una contradicción numérica con el panel OOS/OOT cuando la sesión usaba pesos de muestra.

**Cambios aplicados**:
- `backend_v3/reporting.py`: Se eliminó la función local `_discrimination_metrics` (que duplicaba la lógica de cálculo de AUC/KS y no soportaba pesos). En su lugar, `build_gains_table` ahora importa y utiliza `_pair_auc_ks` desde `validation.py`, que maneja pesos de forma nativa. Esto unifica la matemática, elimina código muerto y resuelve la asimetría del path binario.
- `tests/test_reporting.py`: Se actualizó el test de paridad de pesos uniformes (renombrado a `test_binary_gains_table_uniform_weights_preserve_metrics`). Se añadió `test_binary_gains_table_non_uniform_weights_affect_metrics` para demostrar que los pesos asimétricos alteran el KS/AUC/Gini.

**Hallazgos**:
- La solución evita usar `compute_oos_metrics` para el path binario (lo que habría roto el cálculo en gains tables con menos de 15 filas al exigir `n_groups`). Al usar el kernel `_pair_auc_ks`, se mantiene la independencia de `n_groups` que tenía `_discrimination_metrics`, pero con soporte completo de ponderación.

**Tests**: 435/435 PASSED.

**Referencias**: `docs/design_decisions.md` §13.7; `docs/estado_proyecto.md` (Pendientes).

### 20/10/2026 — Cierre documental D13 y bump a v1.0.0rc3

**Estado**: ✅ Cerrada. Suite 435/435 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=high.

**Revisor**: Marco Rengel.

**Contexto**: Mini-cierre documental para sincronizar todos los archivos tras la resolución de la deuda D13 (ponderación de métricas en la Gains Table binaria) y el bump de versión a `1.0.0rc3`. Kimi detectó cinco desincronizaciones residuales tras el primer bloque de cierre, las cuales se resuelven en esta entrada.

**Cambios aplicados**:
- `README.md` / `README.es.md`: Mermaid actualizado a `435/435` y `v1.0.0rc3`; nota IFRS 9 actualizada a `rc3`.
- `docs/prompt_para_asistente.md`: conteo de tests actualizado a `435/435`.
- `docs/roadmap.md`: narrativa de la Fase 3.5 anotada con la resolución de D13.
- `docs/api.md`, `docs/contexto_para_nueva_sesion.md`, `pyproject.toml`, `frontend_v3/__init__.py`: actualizados en el bloque anterior.

**Hallazgos**:
- El uso del patrón `434/434` en mi prompt anterior falló en el Mermaid porque el archivo usaba `434 / 434` (con espacios). El agente (Kimi) lo detectó al revisar el archivo y no encontrarlo. Lección: usar `grep` o regex en lugar de confiar en un string literal para las sustituciones masivas.

**Tests**: 435/435 PASSED.

**Referencias**: `docs/design_decisions.md` §13.7; `docs/estado_proyecto.md` (Pendientes).

### 20/10/2026 — Saneamiento documental pre-Poda

**Estado**: ✅ Cerrada. Suite 435/435 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=high.

**Revisor**: Marco Rengel.

**Contexto**: La auditoría previa al diseño de la Poda Interactiva detectó contradicciones documentales. Varios documentos afirmaban que `pruning.py` "no estaba integrado en Session", cuando `Session.prune(alpha)` existe desde la Fase 1.2. También se detectó una referencia a una "Phase 2.4" (poda) en los mensajes de i18n que nunca existió en el roadmap.

**Cambios aplicados**:
- `docs/roadmap.md`, `docs/api.md`, `docs/estado_proyecto.md`, `docs/contexto_para_nueva_sesion.md`: corregida la afirmación sobre la integración en Session (ahora reflejan que existe `Session.prune()`, pero falta la GUI).
- `frontend_v3/i18n.py`: eliminada la referencia a "Phase 2.4" en el aviso de árbol grande (EN/ES).

**Tests**: 435/435 PASSED (sin cambios de código, solo i18n).

### 20/10/2026 — Diseño de la Fase 3.9 (Poda Interactiva y Ponderada)

**Estado**: ✅ Cerrada. Suite 435/435 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=high.

**Revisor**: Marco Rengel.

**Contexto**: Tras la auditoría de la Poda (que detectó contradicciones y carencias en la documentación), se ha redactado y aprobado el diseño completo para la Poda Interactiva y Ponderada.

**Cambios aplicados**:
- `docs/methodology.md` §7.1: Añadida la fórmula `r_w(t)` para árboles ponderados.
- `docs/design_decisions.md` §8.5-8.7: Añadidas las decisiones de diseño (ponderación, `Session.get_prune_sequence()`, y GUI `PruneDialog`).
- `docs/roadmap.md`: Registrada la Fase 3.9 como próxima implementación.
- Documentos de contexto y `audit_log`: sincronizados.

**Tests**: 435/435 PASSED (sin cambios de código).

### 20/10/2026 — Implementación del Backend de la Poda (Fase 3.9)

**Estado**: ✅ Cerrada. Suite 437/437 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=max.

**Revisor**: Marco Rengel.

**Contexto**: Implementación del backend de la Poda Coste-Complejidad, siguiendo el diseño aprobado en `design_decisions.md` §8.5-8.6. El objetivo es que la poda utilice la masa ponderada (`w_events`) si el árbol creció con pesos, y exponer la secuencia en `Session` para su futuro uso en la GUI.

**Cambios aplicados**:
- `backend_v3/pruning.py`: Implementación del cálculo ponderado `r_w(t) = sum(w_events) - max(w_events)`. Si `w_events` está vacío, mantiene la paridad exacta con el cálculo de conteos físicos.
- `backend_v3/session_state.py`: Añadido `Session.get_prune_sequence()` (DTO plano vía `dataclasses.asdict`) para que el frontend pueda leer la secuencia.
- `tests/test_pruning.py` y `tests/test_session_state.py`: Añadidos tests de ponderación y de tipos de retorno.

**Auditoría y Correcciones**:
- Se realizó una auditoría forense del código (razonamiento=max) que detectó tres mejoras menores.
- `pruning.py`: El formato del log DEBUG `R=%d` se cambió a `R=%.6g` para no truncar valores ponderados float.
- `design_decisions.md` §8.5: Se añadió una nota aclarando que `r_subtree` ahora es `float` en el DTO.
- `test_session_state.py`: La aserción de tipo para `r_subtree` se hizo estricta (`is float`).

**Tests**: 437/437 PASSED.

### 20/10/2026 — Implementación de la GUI de la Poda y cierre de la Fase 3.9

**Estado**: ✅ Cerrada. Suite 438/438 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=max.

**Revisor**: Marco Rengel.

**Contexto**: Implementación del diálogo interactivo `PruneDialog` (Fase 3.9 §8.7) para permitir al analista visualizar la secuencia de poda y elegir el `alpha` (discrecionalidad tipo CART). Esto cierra la Fase 3.9 completa.

**Cambios aplicados**:
- `frontend_v3/prune_dialog.py`: Nuevo diálogo con `QTableWidget` para mostrar la secuencia.
- `frontend_v3/main_window.py`: Cableado en el menú Model. Se usó `set_model()` en lugar de `refresh()` en el `TreePanel` (desviación documentada) porque el árbol podado es un `TreeModel` nuevo.
- `frontend_v3/i18n.py`: Añadidas las claves del diálogo y corregido un **bug latente**: faltaba la clave `tree_leaf_reason_podado`, que habría causado un `KeyError` al mostrar cualquier árbol podado.
- `tests/test_e2e_mainwindow.py`: Nuevo test E2E del flujo de poda.

**Tests**: 438/438 PASSED.

**Nota**: Publicada finalmente como 1.0.0rc4 en PyPI debido a un conflicto de inmutabilidad con la versión rc3, subida previamente con los cambios de D13.

### 21/10/2026 — Creación del Playbook de Gobernanza

**Estado**: ✅ Cerrada. Suite 438/438 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=high.

**Revisor**: Marco Rengel.

**Contexto**: Se detectó que las fases 3.7, 3.8 y 3.9 se habían implementado sin crear su archivo `docs/X.Y_design_*.md` correspondiente (un patrón de fallo que ya ocurrió en la Fase 3.2). Para prevenirlo, se ha creado un Playbook formal.

**Cambios aplicados**:
- `docs/playbook.md` (nuevo): Define los flujos obligatorios `/nueva_fase`, `/cierre_fase` y `/auditoria_max`.
- Documentos de diseño retrospectivos: Creados `docs/3.7_design_pre_release_fixes.md`, `docs/3.8_design_regulatory_attribution.md` y `docs/3.9_design_interactive_weighted_pruning.md` para cerrar el hueco de gobernanza y alinear la estructura documental con el Playbook.
- `docs/prompt_para_asistente.md`, `.treegovrules`, `AGENTS.md`: Actualizados para exigir la lectura del Playbook antes de generar prompts.

**Tests**: 438/438 PASSED.

### 21/10/2026 — Auditoría Forense y Saneamiento Global Documental

**Estado**: ✅ Cerrada. Suite 438/438 PASSED.

**Modelo**: OpenCode 1.19.0 + `moonshotai/kimi-k3`, reasoning=max.

**Revisor**: Marco Rengel.

**Contexto**: Tras la publicación de `1.0.0rc4`, una revisión visual del README reveló que persistían desincronizaciones (ej. `435 / 435` en el diagrama Mermaid, y la Poda descrita aún como "API-only"). Se ejecutó una auditoría forense en todos los `.md` activos para buscar cualquier rastro de estados anteriores.

**Hallazgos y Correcciones**:
- Se encontraron 9 desincronizaciones en 5 archivos (`README.md`, `README.es.md`, `docs/api.md`, `docs/roadmap.md`, `docs/contexto_para_nueva_sesion.md`).
- Se actualizaron los conteos de tests a `438/438` (incluyendo variantes con espacios).
- Se actualizaron las descripciones de la Poda (Fase 3.9) en los READMEs y en `api.md`, reflejando que es interactiva, ponderada y está en la GUI.
- Se marcaron como "Resueltas" las deudas de Poda y PyPI en `roadmap.md`.
- Se limpió la deuda de Poda en `contexto_para_nueva_sesion.md`.
- Se detectó que la estructura de directorios (`Repository structure`) en los READMEs (EN/ES) no incluía los archivos de diseño retrospectivos (3.7, 3.8, 3.9) ni el `playbook.md`. Ambos árboles fueron actualizados para reflejar la realidad del repositorio.

**Lección Aprendida (Gobernanza)**: Las búsquedas literales (ej. `435/435`) fallan si el documento usa espacios (`435 / 435`). El checklist de cierre de fase debe incluir un `grep` global de patrones obsoletos (con y sin espacios) para evitar que textos descriptivos o diagramas queden anclados en el pasado.

**Tests**: 438/438 PASSED.
