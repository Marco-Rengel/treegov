# TreeGov — Risk Segmentation Workbench

**Versión**: 1.0.0rc9
**Autor**: Marco Rengel
**Licencia**: Apache 2.0
**Motor gráfico**: PySide6
**Motor analítico**: Python (NumPy, pandas, scipy.stats)
**Suite de tests**: 752/752 passing

> ⚠️ **Aviso regulatorio.** TreeGov está en fase de validación técnica (Model Risk Management - MRM). **Uso restringido: validación técnica MRM. No apto para producción bancaria sin aprobación regulatoria.** Cualquier uso en un entorno productivo regulado (bancario o de otro tipo) requiere validación independiente, aprobación formal e integración con el marco de gobierno de modelos de la institución.

**Ámbito de datos.** TreeGov se desarrolla exclusivamente con *datasets* públicos (German Credit, UCI) y datos sintéticos. Está diseñado para uso final con datos bancarios reales en el escritorio del analista: el CSV nunca sale del equipo. Durante el desarrollo no se envían datos reales a APIs de IA de terceros. Cuando TreeGov se use en producción con datos reales, los *logs* DEBUG y los *reports* HTML exportados contienen información sensible del modelo (PD por nodo, conteos por segmento, nombres de columnas reales, rutas de archivo) y deben tratarse como material confidencial por parte del analista.

---

## Resumen ejecutivo

TreeGov es una plataforma *open source* para construir, validar y auditar modelos basados en árboles de decisión en entornos regulados. Nace como heredera de las herramientas GUI clásicas (hoy discontinuadas) que permitían a los analistas construir modelos sin programar. A diferencia de las suites corporativas cerradas, TreeGov democratiza la gobernanza de modelos (MRM) y el cumplimiento de estándares como Basilea e IFRS 9.

El sistema implementa CHAID (clásico y Exhaustive), C&RT y QUEST con matemática de caja blanca: cada fórmula estadística está escrita explícitamente y citada a su publicación original. La gobernanza es *opt-out* a través de dos modos explícitos. El Modo Regulatorio (por defecto) aplica la capa completa de MRM requerida por bancos y burós de crédito: estimador de Jeffreys, PD floor (BCBS CRE 32.4) y huellas criptográficas que registran la elección. El Modo Investigación produce probabilidades empíricas crudas, abriendo la herramienta a dominios como salud, biología o ciencias sociales. La elección es siempre explícita y nunca silenciosa.

Las librerías tradicionales (*scikit-learn*, *statsmodels* o paquetes de R) exigen escribir código, lo que resta tiempo al análisis. Por otro lado, las herramientas visuales que existieron en el pasado fueron discontinuadas. TreeGov llena ese vacío combinando un entorno visual de código abierto con la trazabilidad regulatoria (SR 11-7, Basilea, IFRS 9) como principio de diseño fundamental.

---

## Filosofía

> «Python le da el motor. TreeGov le da el motor, el freno, el tablero, el cinturón de seguridad y el registro de mantenimiento. ¿Cuál prefiere para un modelo que va a ser auditado por el regulador?»

TreeGov parte de una premisa: la gobernanza de modelos no es una capa que se añade al final, sino un principio que se teje en cada componente. Mientras que las librerías estadísticas y los entornos de *scripting* ofrecen el motor analítico, TreeGov ofrece además el freno (controles MRM), el tablero (visualización gráfica), el cinturón de seguridad (auditabilidad) y el registro de mantenimiento (bitácora inmutable). Para un modelo que será auditado por un regulador, la elección no es técnica: es de gobernanza.

Más allá de usar MRM dentro de la herramienta, **el software en sí mismo se construye bajo disciplina MRM**: auditoría de diseño antes del código, supervisión humana en el circuito, verificación adversarial y trazabilidad inmutable para cada release.

TreeGov es un **desarrollo Clean Room**: una reimplementación matemática moderna derivada exclusivamente de papers académicos (Kass, Breiman, Loh & Shih) y del estándar clásico de estaciones de árboles documentado (circa 2001). Toda su lógica es de caja blanca, garantizando la independencia algorítmica y la máxima auditabilidad (`docs/design_decisions.md` §0.5).

*Lee la filosofía completa → [Español](https://github.com/Marco-Rengel/treegov/blob/main/docs/philosophy.es.md) · [English](https://github.com/Marco-Rengel/treegov/blob/main/docs/philosophy.md)*

```mermaid
flowchart TB
    TG["<b>🌳 TreeGov</b><br/>Risk Segmentation Workbench<br/><i>por Marco Rengel</i>"]

    TG --> P["<b>🎯 Propósito</b><br/>Segmentación de riesgo<br/>con gobernanza MRM/IFRS 9"]
    TG --> M["<b>🧮 Motores</b><br/>CHAID · C&RT · QUEST<br/>Caja blanca + citas"]
    TG --> G["<b>🔒 Gobernanza</b><br/>SplitConfig frozen<br/>Fingerprint sha256<br/>Audit log"]
    TG --> S["<b>🛠️ Stack</b><br/>Python 3.11 · PySide6<br/>numpy · pandas · scipy<br/>Apache 2.0"]

    P --> ARQ["<b>🏗️ Arquitectura</b><br/>Sala limpia estricta"]
    M --> ARQ
    G --> ARQ
    S --> ARQ

    ARQ --> BE["<b>backend_v3</b><br/>Capa analítica<br/>cero imports Qt"]
    ARQ --> FE["<b>frontend_v3</b><br/>Capa de presentación<br/>cero imports numpy"]
    ARQ --> MC["<b>mcp_v3</b><br/>Capa MCP<br/>headless, cero imports Qt"]

    BE -.->|Session| FE
    BE -.->|Session| MC

    ARQ --> ST["<b>📊 Estado actual</b><br/>✅ Fases 0 → 7 + 3.12 · 16/16 críticos MRM + MEN-05 cerrados<br/>📦 v1.0.0rc9 (release candidate)<br/>🧪 752 / 752 tests PASSED<br/>📅 20 nov 2026"]

    style TG fill:#0D47A1,color:#fff,stroke:#002171,stroke-width:2px
    style P fill:#2E7D32,color:#fff
    style M fill:#2E7D32,color:#fff
    style G fill:#2E7D32,color:#fff
    style S fill:#2E7D32,color:#fff
    style ARQ fill:#E65100,color:#fff
    style BE fill:#37474F,color:#fff
    style FE fill:#37474F,color:#fff
    style MC fill:#37474F,color:#fff
    style ST fill:#1565C0,color:#fff
```

---

## ¿Qué es TreeGov?

TreeGov es una estación de trabajo analítica para construir, evaluar y auditar árboles de decisión en entornos regulados. A diferencia de las librerías de *machine learning*, donde el analista opera en una caja negra, TreeGov proporciona un entorno visual con matemática explícita y trazabilidad absoluta.

La característica principal de TreeGov es la auditabilidad radical. Absolutamente todo el ciclo de vida del modelo puede ser rastreado por un auditor:
*   El código: cada fórmula estadística está escrita explícitamente y citada a su publicación original.
*   Las decisiones: la arquitectura y los *trade-offs* están documentados para justificar cada elección.
*   El modelo: cada entrenamiento genera un *fingerprint* (huella) único que actúa como sello inmutable.
*   La evidencia: una bitácora transaccional registra cada paso, y una suite de más de 750 pruebas (incluyendo *datasets* públicos validados) garantiza la reproducibilidad de los resultados.

---

## Principios de diseño

1. **Arquitectura de sala limpia bidireccional**: separación estricta entre el backend analítico (`backend_v3/`, sin dependencias de Qt/GUI) y la capa de presentación (`frontend_v3/`, sin lógica analítica), protegida por guardrails AST bidireccionales (`test_frontend_clean_room` y `test_backend_clean_room`).
2. **Caja blanca ampliada**: bloqueo a nivel de intérprete (`backend_v3/import_guard.py`) de *sklearn*, *scikit-learn*, *statsmodels*, *xgboost*, *lightgbm*, *catboost*, *torch*, *optbinning*, *scorecardpy*, *tensorflow* y *keras*, auto-instalado en todos los puntos de entrada (`backend_v3`, `frontend_v3`, `mcp_v3`, `treegov.py`, `treegov_gui.py`, `treegov_mcp.py`, `scripts/validate_uci.py`). Cada fórmula estadística está escrita explícitamente en el código, con su cita bibliográfica.
3. **Gobernanza nativa**: logging transaccional DEBUG, configuración inmutable (*SplitConfig frozen*), clasificación estricta Basilea III CRE 32.4 (`BANKING` / `RESEARCH` / `CUSTOM`), validación obligatoria SR 11-7 (Holdout o CV k-fold) y validación de invariantes matemáticos en la construcción.

---

## Capacidades analíticas

| Capacidad | Referencia | Anclaje regulatorio | Características clave |
|---|---|---|---|
| **CHAID** clásico y Exhaustive | Kass (1980); Biggs et al. (1991); Chan, Golub & LeVeque (1983) | — | Fusión iterativa de categorías con corrección de Bonferroni, soporte multiclase, binning continuo de 10 cortes cuantiles (hasta 11 bins, `(a, b]` con `right=True`), varianza continua centrada y selección elegible por Cochran en Exhaustive CHAID |
| **C&RT** | Breiman et al. (1984); Chan, Golub & LeVeque (1983) | — | Impureza de Gini normalizada (a prueba de overflow/cancelación) / reducción de varianza centrada, *surrogate splits*, multiclase (K ≥ 2) |
| **QUEST** | Loh & Shih (1997); Kish (1965) | — | Selección insesgada de variable, varianza ponderada de confiabilidad de Kish (invariante a escala y segura con pesos normalizados) y raíces cuadráticas estables de Citardauq para QDA en K=2, barrido de Gini para K > 2 (enfoque híbrido C&RT/QUEST para multiclase) |
| **Soporte Multiclase** | Hand & Till (2001) | — | Soporte extremo a extremo K ≥ 3 (incluyendo targets de texto), tabla de ganancias traducida canónicamente, Gini multiclase, KS por pares y matriz de clasificación dinámica K × K en GUI y HTML |
| **Ponderación por muestra** | Heeringa et al. (2010) | SR 11-7 | Ajuste de sesgo muestral en motores, construcción del árbol, métricas de validación y monitoreo de estabilidad. Limitación conocida: el split train/test estratifica por conteo físico de filas (no por masa ponderada) y el agreement de surrogates en C&RT no está ponderado (design_decisions.md §13.3, §13.6.2). El Gini/KS/AUC global de la gains table binaria SÍ está ponderado desde la resolución de D13 (20/10/2026; ver design_decisions.md §13.7). |
| **Categorías de población** | — | — | Filtro *opt-in* para excluir categorías (Indet, No Perf) antes del entrenamiento (trazado en `params_fingerprint`) |
| **Estimador de Jeffreys + PD Floor** | Jeffreys (1946) | BCBS CRE 32.4 | Mitigación de probabilidades nulas en carteras de bajo impago; la clasificación estricta `BANKING` exige `apply_jeffreys=True` y `pd_floor >= 0.0005` (`0.0` o el legado `0.0003` se clasifican como `CUSTOM`) |
| **Partición Hamilton-Hare** | — | — | *Split* train/test estratificado exacto (`Q_j = N_j * train_frac`), rechazo fail-fast de `NaN`, sin sesgo de redondeo |
| **Imputación anti-leakage** | — | SR 11-7 | Estadísticos ajustados solo sobre train (`TrainOnlyImputer`) con rechazo fail-fast de `±inf` |
| **Poda coste-complejidad** | Breiman et al. (1984) | — | Post-poda con la secuencia alpha; reindexado determinista de nodos; modelo podado activo (`Session.active_tree`) conectado a todos los consumidores aguas abajo y al diálogo `PruneDialog` de la GUI con invalidación automática de métricas obsoletas |
| **Validación Out-of-Sample (OOS) / Out-of-Time (OOT)** | Hanley & McNeil (1982); Hosmer & Lemeshow (1980); Hosmer, Lemeshow & Sturdivant (2013) | Basilea; SR 11-7 | Gini, KS, Hosmer-Lemeshow *tie-preserving* invariante al orden de filas con grados de libertad externos `df = G_eff` (Hosmer, Lemeshow & Sturdivant 2013 §5.2.2) y `_HL_EPS = 1e-6`, Brier, ROC/AUC, PR-AUC, `w_accuracy` en binario y `evaluate_oot` compatible con CV |
| **Monitoreo de estabilidad** | Siddiqi (2006) | Basilea / EBA | Population Stability Index (PSI, hojas) y Characteristic Stability Index (CSI, covariables) con `eps` configurable/validado, intervalos `(a, b]` (`right=True`), bin explícito `<MISSING>` para `NaN`, detección de deriva en continuas constantes y `Gini Drop` indefinido (`UNDETERMINED`) cuando `Gini_train <= 0` |
| **Validación con datasets UCI** | UCI ML Repository | — | Reproducibilidad anclada a 6 *datasets* (German Credit, Breast Cancer, etc.) |

---

## Stack tecnológico

- Python 3.11 / 3.12
- PySide6 (interfaz gráfica)
- numpy, pandas, scipy.stats (cálculo estadístico)
- pyarrow, openpyxl (ingesta de datos)
- pytest (opcional: los tests son ejecutables con python directo)

---

## Estructura del repositorio

```
TreeGov/
├── backend_v3/              # Capa analítica pura (0 imports Qt)
│   ├── import_guard.py      # Bloqueo de librerías de caja negra
│   ├── log_config.py        # Logger transaccional DEBUG
│   ├── types.py             # SplitConfig (frozen) + enums
│   ├── statistics.py        # chi2, F, Brown-Forsythe, Stirling, Kass
│   ├── imputation.py        # TrainOnlyImputer (anti-leakage)
│   ├── chaid_engine.py      # CHAID clásico + Exhaustive
│   ├── crt_engine.py        # C&RT multiclase + surrogate splits
│   ├── quest_engine.py      # QUEST multiclase + QDA/Gini
│   ├── splitting.py         # Partición Hamilton-Hare
│   ├── profiling.py         # Inferencia de tipos de predictor
│   ├── tree_builder.py      # Construcción BFS + TreeModel
│   ├── session_state.py     # Máquina de estados (EMPTY a TRAINED a OOT)
│   ├── validation.py        # Métricas OOS + evaluación OOT
│   ├── pruning.py           # Poda coste-complejidad (Breiman)
│   ├── reporting.py         # DTOs de gains table + matriz de clasificación
│   ├── stability.py         # PSI / CSI / Gini Drop
│   ├── exporters.py         # Exportadores de producción SQL / Python / Markdown (Fase 4.0)
│   ├── scoring.py           # Batch scoring + champion-challenger (Fase 6.0)
│   └── ecl.py               # ECL IFRS 9: staging + PD × LGD × EAD (Fase 7.0)
├── frontend_v3/             # Capa de presentación (Fase 2)
├── mcp_v3/                  # Capa MCP, headless (dto, server, tools — Fase 5.0)
├── scripts/                 # Utilidades de infraestructura (descarga, validación, fechas)
├── tests/                   # Tests unitarios (dual: pytest / python directo)
├── docs/                    # Documentación y gobernanza del proyecto
│   ├── api.md               # Public API surface (EN)
│   ├── design_decisions.md  # Implementation decisions (EN)
│   ├── methodology.md       # Mathematical methodology (EN)
│   ├── roadmap.md           # Phase plan and current status (EN)
│   ├── audit_log.md         # Bitácora cronológica (ES)
│   ├── estado_proyecto.md   # Dossier ejecutivo del proyecto (ES)
│   ├── security_audit.md    # Auditoría de seguridad y privacidad (EN)
│   ├── playbook.md          # Playbook de gobernanza y flujos (ES)
│   ├── 3.12_design_analysis_workspace.md # Último diseño de fase + as-built (ES)
│   ├── ( ... y más de 30 documentos de diseño de las fases 3.1 a 7.0, y archivos de contexto ... )
├── archive/                 # Documentos históricos (solo lectura)
├── data/                    # Datasets (solo lectura, Git-ignored)
├── logs/                    # Logs por corrida (Git-ignored)
├── treegov.py               # Orquestador headless (CLI)
├── treegov_gui.py           # Entry point de la GUI (Fase 2)
├── treegov_mcp.py           # Entry point del servidor MCP (console script treegov-mcp, Fase 5.0)
├── pyproject.toml           # Empaquetado
├── requirements.txt         # Mínimos de trabajo (pyproject.toml es la fuente oficial)
├── opencode.json            # Configuración del proyecto OpenCode
├── README.md                # README principal (EN)
├── README.es.md             # Este archivo (ES)
├── AGENTS.md                # Instrucciones operativas para agentes IA
├── CONVENTIONS.md           # Convenciones operativas para Aider
├── LICENSE                  # Apache 2.0
├── NOTICE.md                # Aviso legal y atribución
├── .gitignore               # Exclusiones de Git
├── .aiderignore             # Exclusiones del repo-map de Aider
├── .gitattributes           # Normalización de line endings
├── .aider.conf.example.yml  # Plantilla de configuración de Aider
└── .treegovrules            # Reglas de gobernanza para agentes IA
```

---

## ¿Por qué TreeGov?

| Si necesita... | Utilice... |
|---------------------------------|---------------------|
| Decenas o cientos de algoritmos ML | *scikit-learn* |
| Aprendizaje profundo | *PyTorch* o *TensorFlow* |
| Potenciación del gradiente | *XGBoost* o *LightGBM* |
| **Árboles auditables con gobernanza MRM** | **TreeGov** |

---

## Inicio rápido

### Instalación

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### Demo headless (Fase 0)

```powershell
.\.venv\Scripts\python treegov.py
```

### Benchmark de rendimiento (N=1M)

```powershell
.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42
```

### Suite de tests

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

---

## Estado del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| **0** | Núcleo algorítmico: 4 motores + statistics + imputación | Completada |
| **1** | Flujo transaccional: splitting, profiling, tree_builder, session_state | Completada |
| **1.2** | Evaluación OOS + poda coste-complejidad | Completada |
| **1.3** | Validación OOT + monitoreo PSI/CSI | Completada |
| **2.0-2.2** | GUI con PySide6: esqueleto, wizard transaccional, visor de árbol | Completada |
| **2.3** | Panel de métricas OOS/OOT | Completada |
| **2.4** | Reportes + integración | Completada |
| **2.1.b** | Esquema de validación cruzada k-fold estratificado + guardrail runtime de imports en la capa GUI (backlog post-Fase 7 B2a/B2b, cerrado 02/11/2026) | Completada |
| **3.0** | Cierre documental + parámetros canónicos configurables | Completada |
| **3.1** | Multiclase (target + wizard + alertas en MetricsPanel) | Completada |
| **3.2** | Ponderación por muestra | Completada |
| **3.3** | Categorías Indet / Insufficient / No Perf | Completada |
| **3.4** | Soporte multiclase en C&RT y QUEST | Completada |
| **3.5** | Reportes adaptados para multiclase y ponderación | Completada |
| **3.6.a** | Diseño del plan de validación con datasets públicos | Completada |
| **3.6.b** | Script de descarga + fixtures versionadas | Completada |
| **3.6.c** | Tests de integración + informe de validación | Completada |
| **3.6.d** | Cierre documental de la fase | Completada |
| **3.6.e** | Modo no-bancario: terminología dinámica vía `tr_term` (etiquetas BANKING intactas; RESEARCH neutras) | Completada |
| **3.7** | Cierre Fase 3 + v1.0.0rc1 | Completada |
| **3.7.e** | Correcciones pre-release (H1, H2, pd_floor K=2) | Completada |
| **3.8** | Corrección de atribución regulatoria (BCBS CRE 32.4) + v1.0.0rc2 | Completada |
| **3.9** | Poda Interactiva y Ponderada | Completada |
| **3.10.a** | Rediseño UX/UI: Toolbar, nodos enriquecidos, panel derecho, jerarquía de tema oscuro (H3-H8) | Completada |
| **3.10.b** | Alineación CHAID con continuas: binning automático por cuantiles (10 cortes, hasta 11 bins), `bin_edges` en `SplitConfig`, routing por `np.digitize` (H14) + hotfix visual (H9, H11-H13) | Completada |
| **3.11.a** | Rediseño Base: Tema Colab, pestañas tipo Excel a página completa, Wizard redimensionado, nodos HTML estilo estación clásica | Completada |
| **3.11.a.1** | Hotfix Visual: layout clásico (barra de 8 menús, toolbar compacta icon-only, panel izquierdo de 3 bloques, pestañas inferiores estilo Excel), nodos QPainter "hoja de auditoría", tema claro/oscuro forzado vía QPalette, cortes numéricos en aristas, copia TSV al portapapeles en tablas, Sistema de Diseño GUI | Completada |
| **3.11.b.1** | Backend del Data Viewer: `Session.get_data_preview` (preview crudo del CSV, dict JSON-serializable de tipos nativos, estado vacío sin excepción — §18.7) | Completada |
| **3.11.b.2** | Frontend del Data Viewer: widget `DataViewer` en el panel izquierdo, tabla de solo lectura, aviso de truncamiento, Ctrl+C → TSV, i18n en caliente | Completada |
| **3.11.b.3** | Tree Map: minimapa pasivo en el panel izquierdo (escena independiente, rectángulos planos por nodo, clic → `centerOn` en la vista principal sin tocar zoom/selección, reconstrucción completa ante cambios del modelo, `fitInView` exclusivo del minimapa, resaltado pasivo del nodo actual) | Completada |
| **3.11.b.4** | Project Explorer: bloque del panel izquierdo con el método + fingerprint corto del modelo actual, reseteo a "—" al reconfigurar | Completada |
| **3.11.b.5** | Fila Total del `NodeItem` con `pct_global` (n del nodo / n de la raíz): parámetro obligatorio del constructor, etiqueta vía `tr("tree_node_total")`, formato `Total (<pct_global>) <n>` | Completada |
| **3.11.c.1** | Backend de árboles univariados en lote: `Session.get_univariate_trees(max_depth=3)` — un árbol por predictor con el mismo motor y gobernanza, DTO plano (`predictor`, `gini`, `ks`, `cut_points`) | Completada |
| **3.11.c.2** | Frontend de árboles univariados: `UnivariateDialog` (Predictor \| Gini \| KS \| Cortes), Ctrl+C → TSV (REGLA 4.1.1), exportación CSV, acción del menú Análisis habilitada en TRAINED | Completada |
| **3.11.c.3** | Matriz de costos N×N: `SessionState.cost_matrix` inmutable, `fix_spec(cost_matrix=...)` endurecido, pestaña "Costs" en el diálogo de Opciones Avanzadas; NO entra en `params_fingerprint` aún (§18.8) | Completada |
| **3.11.d** | Menú contextual e interactividad: `Session.intervene_node` (poda manual de rama), re-indexado BFS, log inmutable `manual_overrides`, menú contextual del nodo con confirmación BANKING, `ManualOverrideDialog` + botón "Ver Auditoría" del HUD (§18.9) | Completada |
| **3.11.e** | Reescritura del Tree Map desde cero (Clean Room): layout tidy top-down estilo Reingold-Tilford, conectores ortogonales en 3 tramos, etiquetas `node_id` de tamaño constante en pantalla, colores 100% desde `PALETTES`, navegación bidireccional vía `center_on_node`, estado vacío sin branding | Completada |
| **3.12** | Consulta del modelo: pestañas Rules y Summary, Data Viewer por nodo/partición, tres curvas nativas de ganancias; `Session.get_rules`, `get_summary` y `get_node_cases` | Completada |
| **4.0** | Exportación a producción (SQL/Python/Markdown + integración GUI) | Completada |
| **4.0.1** | Exporters: categorical unseen_policy | Completada |
| **5** | Capa MCP para agentes LLM | Completada |
| **6** | Batch scoring + champion-challenger | Completada |
| **7** | IFRS 9 / ECL (staging, ECL = PD × LGD × EAD) | Completada |
| **Higiene del Repositorio (Fase 1)** | Limpieza de 3.49 GB → ~6 MB (venv externo limpio), `.gitignore`/`.aiderignore` endurecidos, des-rastreo de `archive/legacy_docs/`, saneamiento de rutas en `AGENTS.md` | Completada |
| **Remediación Auditoría MRM (`2A`–`2I`, `v1.0.0rc9`)** | Cierre 16/16 de hallazgos críticos (`CRIT-01`–`CRIT-16`) + `MEN-05` paridad bibliográfica (24 referencias académicas + 4 regulatorias, cero zonas grises de atribución): paridad de exportadores y hoja mayoritaria, gobernanza Basilea III estricta, poda activa (`active_tree`), IFRS 9 staged ECL/EIR, seguridad MCP `TREEGOV_MCP_ROOT`, multiclase K ≥ 3 extremo a extremo y Wizard endurecido, estabilidad numérica de motores, Hosmer-Lemeshow OOS y PSI/CSI, coherencia metodológica SR 11-7 y guardrails bidireccionales de Sala Limpia/Caja Blanca | Completada |

**Suite de tests: 752/752 passing.**

---

## Referencias académicas

- Biggs, D., de Ville, B. & Suen, E. (1991). *A Method of Choosing Multiway Partitions for Classification and Decision Trees*. Journal of Applied Statistics 18(1), 49-62.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). *Classification and Regression Trees*. Wadsworth.
- Brier, G.W. (1950). *Verification of forecasts expressed in terms of probability*. Monthly Weather Review 78(1), 1-3.
- Brown, M.B. & Forsythe, A.B. (1974). *Robust Tests for the Equality of Variances*. Journal of the American Statistical Association 69(346), 364-367.
- Chan, T.F., Golub, G.H. & LeVeque, R.J. (1983). *Algorithms for Computing the Sample Variance: Analysis and Recommendations*. The American Statistician 37(3), 242-247.
- Cochran, W.G. (1954). *Some Methods for Strengthening the Common Chi-2 Tests*. Biometrics 10(4), 417-451.
- Davis, J. & Goadrich, M. (2006). *The relationship between Precision-Recall and ROC curves*. Proceedings of the 23rd International Conference on Machine Learning (ICML), 233-240.
- Fagerland, M.W., Hosmer, D.W. & Bofin, A.M. (2012). *Multinomial goodness-of-fit tests for logistic regression models*. Statistics in Medicine, 31(30), 4238-4253.
- Fisher, R.A. (1925). *Statistical Methods for Research Workers*. Oliver & Boyd, Edinburgh.
- Hand, D.J. & Till, R.J. (2001). *A simple generalisation of the area under the ROC curve for multiple class classification problems*. Machine Learning, 45(2), 171-186.
- Hanley, J.A. & McNeil, B.J. (1982). *The meaning and use of the area under a receiver operating characteristic (ROC) curve*. Radiology 143(1), 29-36.
- Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). *Applied Survey Data Analysis*. Chapman & Hall/CRC.
- Hosmer, D.W. & Lemeshow, S. (1980). *A goodness-of-fit test for the multiple logistic regression model*. Communications in Statistics A10, 1043-1069.
- Hosmer, D.W., Lemeshow, S. & Sturdivant, R.X. (2013). *Applied Logistic Regression* (3rd ed.). Wiley.
- Jeffreys, H. (1946). *An invariant form for the prior probability in estimation problems*. Proceedings of the Royal Society of London A 186(1007), 453-461.
- Kass, G.V. (1980). *An Exploratory Technique for Investigating Large Quantities of Categorical Data*. Applied Statistics 29(2), 119-127.
- Kish, L. (1965). *Survey Sampling*. Wiley.
- Kohavi, R. (1995). *A study of cross-validation and bootstrap for accuracy estimation and model selection*. Proceedings of the 14th International Joint Conference on Artificial Intelligence (IJCAI), 1137-1143.
- Levene, H. (1960). *Robust tests for equality of variances*. In *Contributions to Probability and Statistics*, Stanford University Press, 278-292.
- Loh, W.-Y. & Shih, Y.-S. (1997). *Split Selection Methods for Classification Trees*. Statistica Sinica 7(4), 815-840.
- Massey, F.J. (1951). *The Kolmogorov-Smirnov Test for Goodness of Fit*. Journal of the American Statistical Association 46(253), 68-78.
- Pearson, K. (1900). *On the criterion that a given system of deviations from the probable in the case of a correlated system of variables is such that it can be reasonably supposed to have arisen from random sampling*. Philosophical Magazine Ser. 5, 50(302), 157-175.
- Press, W.H., Teukolsky, S.A., Vetterling, W.T. & Flannery, B.P. (2007). *Numerical Recipes: The Art of Scientific Computing* (3rd ed.), §5.6. Cambridge University Press.
- Siddiqi, N. (2006). *Credit Risk Scorecards: Developing and Implementing Intelligent Credit Scoring*. Wiley.

---

## Referencias regulatorias

- **Basilea (BCBS CRE 32.4)**: suelos regulatorios de PD (0.05% para
  corporativos, bancos y retail; 0.03% o exención para soberanos).
- **EBA/GL/2017/16**: directrices sobre especificación, estimación y validación de parámetros PD/LGD en modelos IRB.
- **IFRS 9 / NIIF 9**: la Fase 7 (endurecida en el Bloque 2C) implementa un motor ECL simplificado de un periodo y escenario único (`PD × LGD × EAD`) con staging determinista, conversión UI `% -> decimal` de EIR, `eir >= 0`, `PD = 1.0` obligatorio en Etapa 3 (default / deterioro crediticio) y provisión combinada por etapa (`total_ecl_staged` / `ecl_applicable`) en backend, GUI y MCP (`docs/7.0_design_ifrs9.md` §5–§6; `docs/design_decisions.md` §29). No certifica cumplimiento IFRS 9 completo; las curvas multi periodo, los escenarios macroeconómicos y la optimización asimétrica de umbrales quedan fuera de su alcance.
- **SR 11-7 / OCC 2011-12**: guía de gestión del riesgo de modelos (MRM).

---

### Capa MCP (Fase 5.0, endurecida en Bloque 2C)
TreeGov expone su backend analítico a agentes LLM mediante el estándar
Model Context Protocol (MCP). La capa es headless (sin imports de GUI) y
expone 27 tools sobre el mismo contrato `Session` que usa la GUI, con
confinamiento estricto a archivos `.csv` dentro de `TREEGOV_MCP_ROOT`
(por defecto `CWD`), bloqueo de sobrescritura y de `output_path == csv_path`
en `score_batch`, validación fail-fast de gobernanza y parámetros, y
serialización `threading.RLock` sobre las 27 herramientas.
Instalación: `pip install treegov[mcp]`
Uso: `treegov-mcp` (arranca el servidor stdio).

## Licencia

Apache License 2.0 — ver [LICENSE](https://github.com/Marco-Rengel/treegov/blob/main/LICENSE).

---

## Contacto

Marco Rengel — marcrengel@gmail.com — github.com/Marco-Rengel

---

## Traducciones

- [English](README.md)
