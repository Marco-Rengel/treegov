# Roadmap de TreeGov

## Completado

- **Fase 0** (núcleo algorítmico): 4 motores + statistics + types +
  import_guard + log_config.
- **Fase 1** (flujo transaccional): splitting + profiling + tree_builder +
  session_state.
- **Fase 1.2** (evaluación OOS + poda): validation + pruning.
  - Suite: 107/107 tests.

## Próximas fases

### Fase 1.3 — Validación OOT y monitoreo básico
**Prioridad: ALTA (imprescindible en riesgo de crédito)**

- Validación Out-of-Time (OOT): cohorte temporal posterior, no partición
  aleatoria.
- Cálculo de Gini Drop (train vs OOS vs OOT).
- Estabilidad poblacional: PSI (hojas) y CSI (covariables) con semáforos
  Basilea / EBA (STABLE < 0.10, MODERATE 0.10-0.25, UNSTABLE >= 0.25).

### Fase 2 — GUI con PySide6
**Prioridad: ALTA (entregable visible)**

- Wizard transaccional (4 pasos).
- Visor de árbol interactivo con zoom.
- Panel de métricas OOS.
- Reporte de poda (comparar árbol original vs podado).

### Fase 3 — Reportes analíticos + Capa MCP
**Prioridad: MEDIA**

- Tabla de ganancias y matriz de clasificación.
- Exportación dual: SQL jerárquico + Python puro.
- Capa MCP (Model Context Protocol) para consumo desde agentes LLM.
  Backend headless como base; MCP como adaptador (no reemplaza la GUI).

### Fase 4 — Scoring batch y producción
**Prioridad: MEDIA**

- Aplicar árbol a cartera completa.
- Champion-challenger: comparar motores y versiones.

### Fase 5 — IFRS 9 / ECL
**Prioridad: BAJA (depende de integración con sistemas bancarios)**

- PD por segmento (hoja del árbol).
- Staging (Stage 1/2/3).
- Cálculo de ECL: PD × LGD × EAD.

## Decisiones arquitectónicas registradas

- **GUI**: PySide6 (no Streamlit). Motivo: política de confidencialidad
  de datos bancarios; los datos no deben salir del escritorio del analista.
- **MCP**: se añade como adaptador en Fase 3, no reemplaza la GUI.
- **Caja blanca**: prohibido sklearn/statsmodels/xgboost/lightgbm/catboost.
- **Gini**: convención 2·AUC − 1 (scoring crediticio).
- **Licencia**: Apache 2.0.

## Decisiones pendientes

- **Distribución**: método de empaquetado (PyInstaller / Inno Setup /
  instalador MSI), firma digital, y canal de distribución. A decidir
  antes de v1.0.
- **Formato de licencia comercial** (si alguna vez se considera): Apache
  2.0 actual es open source; una versión comercial paralela requeriría
  análisis legal.
