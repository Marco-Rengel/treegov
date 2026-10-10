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