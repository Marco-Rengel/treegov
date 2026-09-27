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