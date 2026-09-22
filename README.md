# TreeGov — Risk Segmentation Workbench

**Versión**: 1.0.0a0
**Autor**: Marco Rengel
**Licencia**: Apache 2.0
**Motor gráfico**: PySide6
**Motor analítico**: Python (NumPy, pandas, scipy.stats)
**Aviso regulatorio**: Software en fase de validación técnica (Model Risk Management - MRM).

---

## Filosofía

> "Python le da el motor. TreeGov le da el motor, el freno, el tablero, el cinturón de seguridad y el registro de mantenimiento. ¿Cuál prefiere para un modelo que va a ser auditado por el regulador?"

TreeGov parte de una premisa: la gobernanza de modelos no es una capa que se añade al final, sino un principio que se teje en cada componente. Mientras que las librerías estadísticas y los entornos de scripting ofrecen el motor analítico, TreeGov ofrece además el freno (controles MRM), el tablero (visualización gráfica), el cinturón de seguridad (auditabilidad) y el registro de mantenimiento (bitácora inmutable). Para un modelo que será auditado por un regulador, la elección no es técnica: es de gobernanza.

---

## ¿Qué es TreeGov?

Herramienta de segmentación analítica para riesgo de crédito con gobernanza MRM/IFRS 9 nativa. Implementa CHAID (Kass, 1980), C&RT (Breiman et al., 1984) y QUEST (Loh & Shih, 1997) con matemática de caja blanca auditable.

---

## Principios de diseño

1. **Arquitectura de sala limpia**: separación estricta entre el backend analítico (backend_v3/, sin dependencias de GUI) y la capa de presentación (frontend_v3/, sin lógica analítica).
2. **Caja blanca**: prohibido el uso de sklearn, statsmodels o cualquier librería de caja negra. Cada fórmula estadística está escrita explícitamente en el código con su cita bibliográfica.
3. **Gobernanza nativa**: logging transaccional DEBUG, configuración inmutable (SplitConfig frozen), validación de invariantes matemáticos en construcción.

---

## Capacidades analíticas

- **CHAID clásico y Exhaustive CHAID**: fusión iterativa de categorías con corrección de Bonferroni de Kass (1980), soporte multiclase.
- **C&RT binario**: partición por impureza de Gini (clasificación) y varianza (regresión), con surrogate splits (Breiman et al., 1984).
- **QUEST binario**: selección insesgada de variable (ANOVA + chi-cuadrado + Levene) con punto de corte QDA univariante (Loh & Shih, 1997).
- **Estimador de Jeffreys + PD Floor**: mitigación de probabilidades nulas en carteras de bajo impago (BCBS CRE 20.39).
- **Partición Hamilton-Hare**: split train/test estratificado exacto, sin sesgo de redondeo.
- **Imputación anti-leakage**: TrainOnlyImputer ajustado exclusivamente sobre train_fold.

---

## Stack tecnológico

- Python 3.11 / 3.12
- PySide6 (interfaz gráfica)
- numpy, pandas, scipy.stats (cálculo estadístico)
- pyarrow, openpyxl (ingesta de datos)
- pytest (opcional: los tests son ejecutables con python directo)

---

## Estructura del repositorio

TreeGov/
- backend_v3/  — Capa analítica pura (0 imports Qt)
  - import_guard.py
  - log_config.py
  - types.py
  - statistics.py
  - imputation.py
  - chaid_engine.py
  - crt_engine.py
  - quest_engine.py
- frontend_v3/  — Capa de presentación (placeholder Fase 2)
- tests/  — Tests unitarios
- docs/  — Documentación vigente (methodology.md, audit_log.md, filosofia.md)
- archive/  — Documentos y código históricos (NO editar)
- data/  — Datasets (solo lectura)
- logs/  — Logs de ejecución por corrida
- treegov.py  — Orquestador headless
- requirements.txt  — Dependencias
- .treegovrules  — Reglas de gobernanza para agentes IA

---

## Ejecución

### Instalación

.\.venv\Scripts\python -m pip install -r requirements.txt

### Demo headless (Fase 0)

.\.venv\Scripts\python treegov.py

### Benchmark de rendimiento (N=1M)

.\.venv\Scripts\python tests\benchmark_1m.py --n 1000000 --seed 42

### Suite de tests

.\.venv\Scripts\python -m pytest tests -q

---

## Estado del proyecto

**Fase 0 (núcleo algorítmico)**: completada. 4 motores + imputación + orquestador + benchmark, auditados.
**Fases 1-4 (interfaz, wizard, reportes)**: en desarrollo.

---

## Referencias académicas

- Kass, G.V. (1980). An Exploratory Technique for Investigating Large Quantities of Categorical Data. Applied Statistics 29(2), 119-127.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.
- Loh, W.-Y. & Shih, Y.-S. (1997). Split Selection Methods for Classification Trees. Statistica Sinica 7(4), 815-840.
- Cochran, W.G. (1954). Some Methods for Strengthening the Common Chi-2 Tests. Biometrics 10(4), 417-451.
- Biggs, D., de Ville, B. & Suen, E. (1991). A Method of Choosing Multiway Partitions for Classification and Decision Trees. Journal of Applied Statistics 18(1), 49-62.

---

## Licencia

Apache License 2.0
---

## Contacto

Marco Rengel — marcrengel@gmail.com — github.com/Marco-Rengel