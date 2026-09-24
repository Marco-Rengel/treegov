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