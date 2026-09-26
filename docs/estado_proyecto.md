# TreeGov — Estado del Proyecto y Contexto para Auditoría

**Fecha de última actualización:** 24/09/2026
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
| PyPI | pypi.org/project/treegov |
| Autor | Marco Rengel (marcrengel@gmail.com) |
| Motor gráfico | PySide6 |
| Motor analítico | Python (NumPy, pandas, scipy.stats) |
| Modelo de IA usado en desarrollo | Kimi K3 vía NVIDIA NIM (max reasoning) |

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

### Fases pendientes

- **Fase 2.1.b** — Extras de endurecimiento (validación cruzada, guardrail runtime de imports backend)
- **Fase 2.2** — Visor interactivo de árbol
- **Fase 2.3** — Panel de métricas OOS/OOT
- **Fase 2.4** — Reportes + integración (tabla de ganancias, exportación HTML, tests e2e GUI)
- **Fase 3** — Capa MCP + exportación SQL/Python
- **Fase 4** — Scoring batch y champion-challenger
- **Fase 5** — IFRS 9 / ECL (staging + ECL = PD × LGD × EAD)

---

## 4. Arquitectura

### Principio de sala limpia

- `backend_v3/` — capa analítica pura (0 imports Qt)
- `frontend_v3/` — capa de presentación (placeholder, sin lógica analítica)

### Estructura de directorios

TreeGov/
├── backend_v3/ # Capa analítica pura
├── frontend_v3/ # Capa de presentación PySide6 (app, main_window, wizard, theme, i18n)
├── tests/ # Suite de tests (148 tests)
├── docs/ # Documentación bilingüe
│ ├── methodology.md # Metodología matemática (inglés)
│ ├── api.md # API pública congelada (inglés)
│ ├── roadmap.md # Plan de fases (inglés)
│ ├── philosophy.md # Filosofía (inglés)
│ ├── philosophy.es.md # Filosofía (español)
│ └── audit_log.md # Bitácora de auditoría (español)
├── archive/ # Documentos y código históricos
├── data/ # Datasets (solo lectura, excluido de Git)
├── logs/ # Logs por corrida (excluido de Git)
├── treegov.py # Orquestador headless
├── pyproject.toml # Empaquetado
├── README.md # README principal (inglés)
├── README.es.md # README en español
└── .treegovrules # Reglas de gobernanza para agentes IA


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

Todos los bugs están registrados en `docs/audit_log.md` con trazabilidad numérica.

---

## 7. Suite de tests

| Módulo | Tests |
|---|---|
| statistics.py | 13 |
| chaid_engine.py | 19 |
| crt_engine.py | 15 |
| quest_engine.py | 13 |
| imputation.py | 5 |
| splitting.py | 4 |
| profiling.py | 3 |
| tree_builder.py | 16 |
| session_state.py | 19 |
| validation.py | 8 |
| pruning.py | 6 |
| stability.py | 9 |
| gui_smoke (frontend) | 9 |
| wizard (frontend) | 9 |
| **Total** | **148** |

**Ejecución:** `.\.venv\Scripts\python -m pytest tests -q` → 148/148 PASSED

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

- [x] ~~Sincronizar entradas faltantes de Fase 1 y Fase 1.2 en
      `docs/audit_log.md`~~ — **Resuelto el 24/09/2026**.
- [x] ~~Enlace Filosofía → `docs/philosophy.md` en ambos READMEs~~ — **Resuelto el 24/09/2026**.
- [x] ~~Columna "Regulatory anchor" en la tabla de capacidades analíticas~~ — **Resuelto el 24/09/2026**.
- [x] ~~Aviso regulatorio reforzado con bloque visual (⚠️)~~ — **Resuelto el 24/09/2026**.
- [x] ~~Estado del proyecto visual con emojis/checklist en `roadmap.md`~~ — **Resuelto el 24/09/2026**.
- [x] ~~Bloque "Cómo se refleja esto en el diseño" en `philosophy.md`~~ — **Resuelto el 24/09/2026**.

### Pendientes técnicos

- [ ] **Fase 2.2** — Visor interactivo de árbol (QGraphicsView, zoom,
      selección de nodo).
- [ ] **Fase 2.1.b** — CV scheme + guardrail runtime de imports backend.
- [ ] Publicar `treegov 1.0.0a1` en PyPI (al cierre de Fase 2).
- [ ] Añadir `pyproject.toml` en la raíz del repo (antes del cierre de
      Fase 2).
- [ ] Datasets públicos (German Credit, UCI health/social) para
      validación multi-dominio (Fase 3).

### Pendientes de CV y carrera profesional

- [ ] **Solicitar contrato a RRHH (Banco de Loja)** — acción personal,
      fuera del proyecto.
- [ ] Revisar cláusula de propiedad intelectual del contrato.
- [ ] Regenerar PDF del CV (encoding UTF-8 roto en encabezado).
- [ ] Mover sección "Idiomas" a la parte superior del CV.
- [ ] Añadir "IA agéntica" a Habilidades del CV.
- [ ] Agregar TreeGov al CV (formulación personal/open source) —
      depende de la cláusula IP.
- [ ] Actualizar LinkedIn con mención genérica de TreeGov (sin enlace al
      repo) — decisión estratégica.

### Pendientes diferidos / estructurales

- [ ] `CONTRIBUTING.md` en el repo (bloqueado por contrato).
- [ ] `docs/i18n/` para centralizar traducciones (cuando haya 5+ docs
      bilingües).
- [ ] Mnemonics `&` en menús GUI (Fase 2.3).
- [ ] QSettings persistencia de parámetros de gobernanza (Fase 2.1.b).
- [ ] QThread para entrenamiento largo (Fase 2.3+).
- [ ] Firma digital + instalador PyInstaller/Inno Setup (Fase 4).
- [ ] Licencia comercial paralela (análisis legal si se considera).

### Decisiones de largo plazo

- [ ] **Distribución:** método de empaquetado, firma digital, canal.
- [ ] **Publicación del repo en GitHub:** pendiente de revisar contrato
      laboral antes de hacerlo público.

---

## 11. Cómo reconstruir el contexto en una nueva sesión

Si se inicia una conversación nueva (con un agente de IA o con un colaborador):

1. Leer en orden:
   - `README.md` (inglés) o `README.es.md` (español)
   - `.treegovrules` (reglas de gobernanza)
   - `docs/methodology.md` (metodología matemática)
   - `docs/api.md` (API pública)
   - `docs/roadmap.md` (plan de fases)
   - `docs/audit_log.md` (histórico de decisiones)

2. Comando para retomar el desarrollo:

cd "C:\Riesgos - copia\DecisionTree_Modeler"
git pull
opencode -c



3. Primer mensaje sugerido al agente:
> "Retomamos TreeGov. Fases 0, 1, 1.2, 1.3, 2.0, 2.1 cerradas.
> Suite 148/148. Decidir siguiente fase: [Fase 2.2 visor de árbol /
> cierre documental / Fase 3]."

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


