# TreeGov — Risk Segmentation Workbench

**Versión**: 1.0.0a0
**Autor**: Marco Rengel
**Licencia**: Apache 2.0
**Motor gráfico**: PySide6
**Motor analítico**: Python (NumPy, pandas, scipy.stats)
**Suite de tests**: 167/167 passing

> ⚠️ **Aviso regulatorio.** TreeGov está en fase de validación técnica (Model Risk Management - MRM). **Uso restringido: validación técnica MRM. No apto para producción bancaria sin aprobación regulatoria.** Cualquier despliegue en producción requiere validación independiente, aprobación formal e integración con el marco de gobierno de modelos de la institución.

---

## Resumen ejecutivo

TreeGov es una estación de trabajo analítica para **segmentación de riesgo de crédito** con **gobernanza de modelos (MRM)** e **IFRS 9** nativas. Implementa los tres algoritmos clásicos de árboles de decisión — CHAID, C&RT y QUEST — con **matemática de caja blanca**: cada fórmula estadística está escrita explícitamente en el código y citada a su publicación original.

A diferencia de las librerías de propósito general (scikit-learn, statsmodels, paquetes de R) que exigen programar, TreeGov ofrece un **entorno gráfico** donde el analista se concentra en el análisis, no en el código. A diferencia de las herramientas GUI descontinuadas, es open source, mantenida activamente, y construida desde cero con la trazabilidad regulatoria (SR 11-7, Basilea, IFRS 9) como principio de diseño de primera clase.

---

## Filosofía

> "Python le da el motor. TreeGov le da el motor, el freno, el tablero, el cinturón de seguridad y el registro de mantenimiento. ¿Cuál prefiere para un modelo que va a ser auditado por el regulador?"

TreeGov parte de una premisa: la gobernanza de modelos no es una capa que se añade al final, sino un principio que se teje en cada componente. Mientras que las librerías estadísticas y los entornos de scripting ofrecen el motor analítico, TreeGov ofrece además el freno (controles MRM), el tablero (visualización gráfica), el cinturón de seguridad (auditabilidad) y el registro de mantenimiento (bitácora inmutable). Para un modelo que será auditado por un regulador, la elección no es técnica: es de gobernanza.

*Lee la filosofía completa → [Español](docs/philosophy.es.md) · [English](docs/philosophy.md)*

---

## ¿Qué es TreeGov?

Herramienta de segmentación analítica para riesgo de crédito con gobernanza MRM/IFRS 9 nativa. Implementa CHAID (Kass, 1980), C&RT (Breiman et al., 1984) y QUEST (Loh & Shih, 1997) con matemática de caja blanca auditable.

---

## Principios de diseño

1. **Arquitectura de sala limpia**: separación estricta entre el backend analítico (`backend_v3/`, sin dependencias de GUI) y la capa de presentación (`frontend_v3/`, sin lógica analítica).
2. **Caja blanca**: prohibido el uso de sklearn, statsmodels o cualquier librería de caja negra. Cada fórmula estadística está escrita explícitamente en el código, con su cita bibliográfica.
3. **Gobernanza nativa**: logging transaccional DEBUG, configuración inmutable (`SplitConfig` frozen), y validación de invariantes matemáticos en la construcción.

---

## Capacidades analíticas

| Capacidad | Referencia | Anclaje regulatorio | Características clave |
|---|---|---|---|
| **CHAID** clásico y Exhaustive | Kass (1980); Biggs et al. (1991) | — | Fusión iterativa de categorías con corrección de Bonferroni, soporte multiclase, regla de Cochran |
| **C&RT** binario | Breiman et al. (1984) | — | Impureza de Gini / varianza, surrogate splits para valores nulos |
| **QUEST** binario | Loh & Shih (1997) | — | Selección insesgada de variable (ANOVA + chi-cuadrado + Levene), corte QDA univariante |
| **Estimador de Jeffreys + PD Floor** | — | BCBS CRE 20.39 | Mitigación de probabilidades nulas en carteras de bajo impago |
| **Partición Hamilton-Hare** | — | — | Split train/test estratificado exacto, sin sesgo de redondeo |
| **Imputación anti-leakage** | — | SR 11-7 | Estadísticos ajustados solo sobre train (`TrainOnlyImputer`) |
| **Poda coste-complejidad** | Breiman et al. (1984) | — | Post-poda con la secuencia alpha; reindexado determinista de nodos |
| **Validación OOS / OOT** | — | Basilea; SR 11-7 | Gini, KS, HL, Brier, ROC/AUC, PR-AUC; soporte de cohorte out-of-time |
| **Monitoreo de estabilidad** | Siddiqi (2006) | Basilea / EBA | PSI (hojas), CSI (covariables), Gini Drop con semáforos |

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
│   ├── crt_engine.py        # C&RT binario + surrogate splits
│   ├── quest_engine.py      # QUEST binario + QDA univariante
│   ├── splitting.py         # Partición Hamilton-Hare
│   ├── profiling.py         # Inferencia de tipos de predictor
│   ├── tree_builder.py      # Construcción BFS + TreeModel
│   ├── session_state.py     # Máquina de estados (EMPTY a TRAINED a OOT)
│   ├── validation.py        # Métricas OOS + evaluación OOT
│   ├── pruning.py           # Poda coste-complejidad (Breiman)
│   └── stability.py         # PSI / CSI / Gini Drop
├── frontend_v3/             # Capa de presentación (Fase 2)
├── tests/                   # Tests unitarios (dual: pytest / python directo)
├── docs/                    # Documentación
│   ├── methodology.md       # Metodología matemática (EN)
│   ├── api.md               # API pública (EN)
│   ├── roadmap.md           # Plan de fases (EN)
│   ├── philosophy.md        # Filosofía (EN)
│   ├── philosophy.es.md     # Filosofía (ES)
│   ├── estado_proyecto.md   # Dossier de estado del proyecto (ES)
│   ├── audit_log.md         # Bitácora de auditoría (ES)
│   ├── contexto_para_nueva_sesion.md  # Bootstrap entre sesiones (ES)
│   └── prompt_para_asistente.md       # Brief para asistentes IA (ES)
├── archive/                 # Documentos históricos (solo lectura)
├── data/                    # Datasets (solo lectura, Git-ignored)
├── logs/                    # Logs por corrida (Git-ignored)
├── treegov.py               # Orquestador headless (CLI)
├── treegov_gui.py           # Entry point de la GUI (Fase 2)
├── pyproject.toml           # Empaquetado
├── README.md                # README principal (EN)
├── README.es.md             # Este archivo (ES)
├── AGENTS.md                # Instrucciones operativas para agentes IA
├── LICENSE                  # Apache 2.0
├── .gitignore               # Exclusiones de Git
└── .treegovrules            # Reglas de gobernanza para agentes IA
```

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
| **2.3** | Panel de métricas OOS/OOT | En progreso |
| **2.4** | Reportes + integración | Planificada |
| **3** | Reportes analíticos + capa MCP para agentes LLM | Planificada |
| **4** | Scoring batch + champion-challenger | Planificada |
| **5** | IFRS 9 / ECL (staging, ECL = PD x LGD x EAD) | Planificada |

**Suite de tests: 167/167 passing.**

---

## Referencias académicas

- Kass, G.V. (1980). *An Exploratory Technique for Investigating Large Quantities of Categorical Data*. Applied Statistics 29(2), 119-127.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). *Classification and Regression Trees*. Wadsworth.
- Loh, W.-Y. & Shih, Y.-S. (1997). *Split Selection Methods for Classification Trees*. Statistica Sinica 7(4), 815-840.
- Cochran, W.G. (1954). *Some Methods for Strengthening the Common Chi-2 Tests*. Biometrics 10(4), 417-451.
- Biggs, D., de Ville, B. & Suen, E. (1991). *A Method of Choosing Multiway Partitions for Classification and Decision Trees*. Journal of Applied Statistics 18(1), 49-62.
- Siddiqi, N. (2006). *Credit Risk Scorecards: Developing and Implementing Intelligent Credit Scoring*. Wiley.

---

## Referencias regulatorias

- **Basilea (BCBS CRE 20.39)**: suelos regulatorios de PD.
- **EBA/GL/2017/16**: directrices sobre especificación, estimación y validación de parámetros PD/LGD en modelos IRB.
- **IFRS 9 / NIIF 9**: clasificación por etapas (staging), ECL, y optimización de umbrales asimétricos.
- **SR 11-7 / OCC 2011-12**: guía de gestión del riesgo de modelos (MRM).

---

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).

---

## Contacto

Marco Rengel — marcrengel@gmail.com — github.com/Marco-Rengel

---

## Traducciones

- [English](README.md)