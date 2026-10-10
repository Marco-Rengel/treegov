# TreeGov — Estado del Proyecto y Contexto para Auditoría

**Fecha de última actualización:** 09/10/2026
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
| Versión | 1.0.0a0 (alpha) |
| Licencia | Apache 2.0 |
| GitHub | github.com/Marco-Rengel/treegov (privado) |
| PyPI | pypi.org/project/treegov/1.0.0a1 |
| Autor | Marco Rengel (marcrengel@gmail.com) |
| Motor gráfico | PySide6 |
| Motor analítico | Python (NumPy, pandas, scipy.stats) |
| Modelo de IA en desarrollo | OpenCode 1.18.35 (cliente activo desde 09/10/2026) + Kimi K3 vía Moonshot AI directo con key propia de Moonshot (NO vía NVIDIA NIM). Aider 0.86.2 como respaldo documentado (pipx, Python 3.11.9). Migración de NVIDIA NIM a Moonshot el 03/10/2026 (factura 2846-0745, NOVASCENT/Singapur) por inestabilidad de NIM (504 recurrentes) |

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

### Fase 2.2 — Visor interactivo de árbol ✅ Cerrada 25/09/2026

Módulos:
- `frontend_v3/tree_view.py` — NodeItem, TreeScene, TreeView, TreePanel
  (zoom idempotente, layout determinista Reingold-Tilford, retraducción en
  caliente, recoloreo por tema).
- Extensión de `main_window.py`: pestaña Tree con HUD de propiedades del nodo.

### Fase 2.3 — Panel de métricas OOS/OOT ✅ Cerrada 29/09/2026

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

### Fase 2.4 — Reportes + integración ✅ Cerrada 03/10/2026

Sub-pasos:
- 2.4.a Diseño estructural ✅ (01/10/2026) — Pestaña Reports +
  `reports_panel.py` (placeholder) + 2 claves i18n + tests ajustados.
- 2.4.b Backend de reportes (`GainsTable` + `ClassificationMatrix`) ✅ (03/10/2026)
- 2.4.c.1 Backend de Session (`get_gains_table` + `get_classification_matrix`) ✅ (03/10/2026)
- 2.4.c.2.a Panel funcional (`reports_panel.py` + i18n) ✅ (03/10/2026)
- 2.4.c.2.b Cableado MainWindow ✅ (03/10/2026)
- 2.4.c.2.c.1 Export HTML ✅ (03/10/2026)
- 2.4.c.2.c.2 Limpieza i18n ✅ (03/10/2026)
- 2.4.c.2.c.3 Tests del panel ✅ (03/10/2026)
- **2.4.c.2 completa** ✅ (03/10/2026)
- 2.4.d Tests E2E + cierre ✅ (03/10/2026)
- **Fase 2.4 completa** ✅ (03/10/2026)

Diseño completo en `docs/roadmap.md` (sección Fase 2.4).

### Fase 3.0 — Cierre de zona gris documental ✅ Cerrada 04/10/2026

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

### Fase 3.1 — Multiclase ✅ Cerrada 09/10/2026

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
- 3.1.a — `TreeNode`/`TreeModel` tuple fields + `TreeBuilder.target_class` ✅ (04/10/2026)
- 3.1.b — Jeffreys multivariante + floor renormalizado + reordenamiento ✅ (integrado en 3.1.a)
- 3.1.c — `Session.fix_spec` + `SessionState` + bloqueo C&RT/QUEST ✅ (05/10/2026)
- 3.1.d — `predict_pd` 2D + bloqueos en validation/reporting/stability ✅ (09/10/2026)
- 3.1.e — Wizard multiclase: tabla de clases + counts + warning minoritaria ✅ (09/10/2026)
- 3.1.f — MetricsPanel: badge Gini negativo + botón de reversión ✅ (09/10/2026)

CHAID y CHAID_EXHAUSTIVE son los únicos motores que admiten K>2 en 3.1;
C&RT y QUEST se abren en Fase 3.4. Las métricas y reportes siguen
binarios hasta Fase 3.5. Invariante no negociable: para K=2 con
target_class=1 y labels estándar, el modelo es numéricamente idéntico
al pre-3.1.

### Fases pendientes

- **Fase 2.1.b** — Extras de endurecimiento (validación cruzada, guardrail runtime de imports backend)
- **Fase 3.2** — Ponderación por muestra (transversal al backend)
- **Fase 3.3** — Categorías Indet / Insufficient / No Perf
- **Fase 3.4** — CRT y QUEST multiclase
- **Fase 3.5** — Reportes adaptados (multiclase + ponderación)
- **Fase 3.6** — Validación con datasets públicos (German Credit, UCI)
- **Fase 3.6.b** — Modo no-bancario (terminología + ejemplos + docs)
- **Fase 3.7** — Cierre Fase 3 + v1.0.0 estable
- **Fase 4** — Reportes avanzados + export (SQL anidado, Python puro, reglas MD/JSON, doc automática)
- **Fase 5** — Capa MCP
- **Fase 6** — Scoring batch y champion-challenger
- **Fase 7** — IFRS 9 / ECL (staging + ECL = PD × LGD × EAD)

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
│ # metrics_panel, theme, i18n)
├── tests/ # Suite de tests (243 tests)
├── docs/ # Documentación bilingüe
│ ├── methodology.md
│ ├── design_decisions.md
│ ├── 3.1_design_multiclass.md
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
├── pyproject.toml # Empaquetado
├── CONVENTIONS.md # Convenciones operativas para Aider
├── AGENTS.md # Instrucciones para agentes IA
├── README.md # README principal (inglés)
├── README.es.md # README en español
├── .gitignore # Exclusiones de Git
├── .aiderignore # Exclusiones del repo-map de Aider
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
| **Idioma de documentación** | Inglés por defecto (estándar open source); bilingüe README y philosophy; audit_log en español (histórico interno) |
| **Anti-leakage** | TrainOnlyImputer exclusivo sobre fold de entrenamiento |
| **OOT como archivo externo** | Nunca como partición aleatoria: validación temporal independiente |
| **GovernanceMode opcional (Fase 2.1)** | BANKING por defecto (Jeffreys + PD Floor, BCBS CRE 20.39); RESEARCH (PD cruda k/n sin floor) abre la herramienta a dominios no bancarios. Trazabilidad: el fingerprint del modelo etiqueta el modo efectivo (BANKING/RESEARCH/CUSTOM) |
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
| statistics.py | 13 |
| chaid_engine.py | 19 |
| crt_engine.py | 15 |
| quest_engine.py | 17 |
| imputation.py | 5 |
| splitting.py | 4 |
| profiling.py | 3 |
| tree_builder.py | 20 |
| session_state.py | 44 |
| validation.py | 11 |
| pruning.py | 6 |
| stability.py | 13 |
| reporting.py | 12 |
| gui_smoke (frontend) | 9 |
| wizard (frontend) | 12 |
| tree_view (frontend) | 10 |
| metrics_panel (frontend) | 13 |
| e2e_mainwindow (frontend) | 6 |
| reports_panel (frontend) | 7 |
| e2e_reports (frontend) | 4 |
| **Total** | **243** |

**Ejecución:** `.\.venv\Scripts\python -m pytest tests -q` → 243/243 PASSED

**Filosofía de tests:** valores de referencia verificados a mano, con cita bibliográfica. No se aceptan tests de autoreferencia.

---

## 8. Estándares regulatorios cubiertos

- **Basilea (BCBS CRE 20.39)** — PD Floors regulatorios (mínimo 0.03% / 3 bps)
- **EBA/GL/2017/16** — Validación de parámetros PD/LGD en modelos IRB
- **IFRS 9 / NIIF 9** — Staging, ECL, optimización de umbrales asimétricos
- **SR 11-7 / OCC 2011-12** — Model Risk Management (MRM)

---

## 9. Repositorios y recursos

| Recurso | Ubicación |
|---|---|
| GitHub | https://github.com/Marco-Rengel/treegov |
| PyPI | https://pypi.org/project/treegov/ |
| Instalación | `pip install treegov` |
| Suite de tests | `.\.venv\Scripts\python -m pytest tests -q` |
| Demo headless | `.\.venv\Scripts\python treegov.py` |
| Benchmark N=1M | `.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42` |

---

## 10. Pendientes y decisiones abiertas

### Sesión documental — ✅ Bloque completo (24/09/2026)

- [x] Sincronizar entradas faltantes de Fase 1 y Fase 1.2 en `docs/audit_log.md` — **Resuelto el 24/09/2026**.
- [x] Enlace Filosofía → `docs/philosophy.md` en ambos READMEs — **Resuelto el 24/09/2026**.
- [x] Columna "Regulatory anchor" en la tabla de capacidades analíticas — **Resuelto el 24/09/2026**.
- [x] Aviso regulatorio reforzado con bloque visual (⚠️) — **Resuelto el 24/09/2026**.
- [x] Estado del proyecto visual con emojis/checklist en `roadmap.md` — **Resuelto el 24/09/2026**.
- [x] Bloque "Cómo se refleja esto en el diseño" en `philosophy.md` — **Resuelto el 24/09/2026**.

### Pendientes técnicos

- [x] **Decisión de proveedor de IA** — migrado a Moonshot AI directo el 03/10/2026. Ver `audit_log.md`.
- [x] **Herramienta activa de desarrollo** — OpenCode 1.18.35 desde el 09/10/2026 (Aider 0.86.2 queda como respaldo documentado). Ver `audit_log.md`.
- [x] **Fase 2.4** — Reportes + integración. Completada el 03/10/2026.
- [x] **Fase 3.0** — Cierre de zona gris documental + 4 parámetros canónicos. Completada el 04/10/2026.
- [x] **Fase 3.1** — Multiclase (6 sub-fases a-f). Completada el 09/10/2026.
- [ ] **Fase 3.2** — Ponderación por muestra (transversal al backend). **Próximo paso.**
- [ ] **Fase 2.1.b** — CV scheme + guardrail runtime de imports backend.
- [x] **Publicar `treegov 1.0.0a1` en PyPI** — completado el 03/10/2026. URL: https://pypi.org/project/treegov/1.0.0a1/
- [ ] Datasets públicos (German Credit, UCI health/social) para validación multi-dominio (Fase 3).
- [ ] `requirements.txt` vs `pyproject.toml` — decidir fuente oficial.

### Pendientes de CV y carrera profesional

- [ ] **Solicitar contrato a RRHH (Banco de Loja)** — acción personal, fuera del proyecto.
- [ ] Revisar cláusula de propiedad intelectual del contrato.
- [ ] Regenerar PDF del CV (encoding UTF-8 roto en encabezado).
- [ ] Mover sección "Idiomas" a la parte superior del CV.
- [ ] Añadir "IA agéntica" a Habilidades del CV.
- [ ] Agregar TreeGov al CV (formulación personal/open source) — depende de la cláusula IP.
- [ ] Actualizar LinkedIn con mención genérica de TreeGov (sin enlace al repo) — decisión estratégica.

### Pendientes diferidos / estructurales

- [ ] `CONTRIBUTING.md` en el repo (bloqueado por contrato).
- [ ] `docs/i18n/` para centralizar traducciones (cuando haya 5+ docs bilingües).
- [ ] Mnemonics `&` en menús GUI (Fase 2.3).
- [ ] QSettings persistencia de parámetros de gobernanza (Fase 2.1.b).
- [ ] QThread para entrenamiento largo (Fase 2.3+).
- [ ] Firma digital + instalador PyInstaller/Inno Setup (Fase 4).
- [ ] Licencia comercial paralela (análisis legal si se considera).

### Decisiones de largo plazo

- [ ] **Distribución:** método de empaquetado, firma digital, canal.
- [ ] **Publicación del repo en GitHub:** pendiente de revisar contrato laboral antes de hacerlo público.

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
> 3.0 y 3.1 (multiclase) cerradas. Suite 243/243. Próximo paso: Fase 3.2
> (ponderación por muestra) con OpenCode 1.18.35 + Kimi K3 vía Moonshot
> AI directo (key propia)."

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