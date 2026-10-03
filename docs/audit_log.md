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