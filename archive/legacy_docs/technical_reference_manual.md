> **[DOCUMENTO HISTÓRICO — era pre-TreeGov]** 
> Este documento fue parte del proyecto DecisionTree_Modeler (fases previas 
> a la reconstrucción de TreeGov, septiembre 2026). Se conserva como 
> evidencia de auditoría. No forma parte de la documentación vigente.
> Para la documentación actual, ver docs/methodology.md y docs/audit_log.md.

# Manual de Referencia Técnica y Arquitectura — Decision Tree Modeler

**Software:** Decision Tree Modeler - Risk Workbench  
**Versión:** 0.9.0-beta (Arquitectura Greenfield Frontend v2)  
**Marco Normativo:** Model Risk Management (MRM - SR 11-7 / OCC 2011-12) & IFRS 9 / Basilea  
**Fecha de Consolidación:** Septiembre 2026  

---

## 1. Arquitectura del Sistema y Principio de Desacoplamiento (Clean Room)

La arquitectura `frontend_v2` implementa una estrategia de diseño *Clean Room* para la capa de presentación visual, manteniendo una separación estricta e inmutable con el motor analítico subyacente (`backend/`):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND V2 (Presentación)                     │
│  ┌───────────────────────┐  ┌───────────────────────────────────────┐  │
│  │   VariableExplorer    │  │            TreeCanvasView             │  │
│  │  (Panel Colapsable)   │  │   (QGraphicsView - Lienzo Infinito)   │  │
│  └───────────────────────┘  └───────────────────┬───────────────────┘  │
│                                                 │                      │
│                                       ┌─────────┴─────────┐            │
│                                       │   HUD Operativo   │            │
│                                       │ (Métricas Estado) │            │
│                                       └───────────────────┘            │
├────────────────────────────────────────────────────────────────────────┤
│                  ORQUESTADOR CENTRAL (MainWindow)                      │
│   • Central Window Registry (self._active_reports)                     │
│   • MRM Transactional Guard (Gobernanza de Excepciones)                │
├────────────────────────────────────────────────────────────────────────┤
│                    VENTANAS FLOTANTES DESACOPLADAS                     │
│   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────┐  │
│   │ ModelSummary  │ │  GainsTable   │ │ ClassifMatrix │ │ Stability │  │
│   │    Widget     │ │    Widget     │ │    Widget     │ │  Monitor  │  │
│   └───────────────┘ └───────────────┘ └───────────────┘ └───────────┘  │
├────────────────────────────────────────────────────────────────────────┤
│                        BACKEND ANALÍTICO (Core)                        │
│   • DecisionTree (Árbol, Poda, Partición, Freeze)                      │
│   • SplitEngine (CHAID, CRT, Chi-cuadrado, Gini, Missing)              │
│   • RuleExporter (SQL CASE WHEN, Python function)                      │
└────────────────────────────────────────────────────────────────────────┘
```

### Reglas de Integración:
1. **Inmutabilidad del Backend:** El código en `backend/` nunca debe modificarse para adaptar firmas o atajos del frontend. Toda orquestación y mediación de tipos reside exclusivamente en `frontend_v2`.
2. **Erradicación de QDockWidget Rígidos:** Toda salida analítica se despliega en ventanas flotantes independientes (`ReportWindow`), preservando el 100% del área gráfica para la exploración interactiva del árbol.

---

## 2. Control de Concurrencia Visual y Gestión del HUD Flotante

### 2.1 Principio de Segregación de Métricas
Para prevenir colisiones visuales, sobrecarga cognitiva y redundancia de datos entre la vista gráfica y las tablas estadísticas, se establece una división estricta de responsabilidades:

- **HUD Flotante (`TreeCanvasHUD` en `frontend_v2/canvas.py`):**
  - Restringido exclusivamente a **métricas operativas de estado local e infraestructura del árbol**:
    - `ID de Nodo`: Identificador único del nodo seleccionado o explorado.
    - `Población (N)`: Frecuencia de registros asignados al nodo y porcentaje sobre el total muestral.
    - `Profundidad del Árbol`: Nivel jerárquico máximo alcanzado en la topología actual.
    - `Nodos Terminales`: Cantidad de hojas activas del árbol de decisión.
  - **Exclusión Explícita:** Se prohíbe la duplicación de métricas estadísticas globales (Bad Rate poblacional, Gini global, KS consolidado) en el HUD, delegando su visualización formal al módulo `ModelSummaryWidget`.

### 2.2 Mecanismo de Ocultamiento Dinámico y Persistencia de Estado
El HUD incorpora un ciclo de vida con estado explícito de visibilidad:
- **Botón de Cierre Integrado:** Ubicado en la esquina superior del panel HUD (`btn_close = QPushButton("✕")`), permite colapsar la superposición en cualquier momento.
- **Bandera `is_explicitly_hidden`:** Cuando el usuario cierra el HUD, se activa la bandera booleana interna. Las rutinas de renderizado (`render_tree`) o selección de nodos (`on_node_selected`) respetan estrictamente este estado y no reabren involuntariamente el HUD.
- **Conmutador Global de Vista:** Accesible mediante el menú superior `Ver -> Conmutar Visor HUD Flotante` y el atajo de teclado estándar **`Ctrl+H`**, que invoca `TreeCanvasView.toggle_hud()` para alternar de forma segura la visibilidad.

---

## 3. Política Centralizada de Gestión de Ventanas (Window Management)

### 3.1 Registro Centralizado (`self._active_reports`)
En arquitecturas basadas en `QGraphicsView` con múltiples ventanas de diagnóstico flotantes (`ReportWindow` basadas en `QMainWindow`), el ciclo de vida de los widgets debe gestionarse de forma determinista para prevenir fugas de memoria y accesos a punteros C++ huérfanos (*Dangling Pointers / Segmentation Faults*).

La clase `MainWindow` implementa un registro central unificado:
```python
self._active_reports: dict[str, ReportWindow] = {}
```

Cada ventana instanciada mediante `_get_or_create_report_window` se asocia a su clave identificadora (`_win_summary`, `_win_gains`, `_win_matrix`, `_win_validation`, `_win_stability`, `_win_audit`).

### 3.2 Protocolo de Destrucción Segura No Destructiva
Cuando se destruye una ventana contenedor en PySide6/Qt, si se invoca directamente `deleteLater()` sobre el `QMainWindow`, Qt destruye en cascada su widget central (`centralWidget`). Para evitar la eliminación del widget analítico de fondo (lo cual impediría reabrir el reporte posteriormente), el protocolo de purga ejecuta una secuencia de desacoplamiento de 3 pasos:

```python
def _close_all_report_windows(self) -> None:
    for attr, win in list(self._active_reports.items()):
        if win is not None:
            try:
                # 1. Desvincular el widget analítico del QMainWindow
                win.takeCentralWidget()
                # 2. Cerrar la ventana del sistema operativo
                win.close()
                # 3. Marcar el contenedor QMainWindow para recolección en Qt
                win.deleteLater()
            except Exception:
                pass
            setattr(self, attr, None)
    self._active_reports.clear()
```

### 3.3 Disparadores Obligatorios de Purga
La rutina `_close_all_report_windows()` se ejecuta de forma síncrona en los siguientes eventos críticos del ciclo de vida:
1. **Carga de Dataset (`load_data`):** Al importar un nuevo archivo CSV, Parquet o Excel, todas las ventanas de reportes previas son cerradas y destruidas antes de instanciar el nuevo marco de datos.
2. **Reinicio de Espacio de Trabajo (`_reset_workspace`):** Restablece la aplicación al estado cero (Zero-State), limpiando variables, árboles y reportes.
3. **Limpieza de Árbol (`clear_tree`):** Invocada desde la barra de herramientas o el menú `Edición -> Limpiar Árbol Activo`.
4. **Cierre de la Aplicación (`closeEvent`):** Garantiza que al salir del programa se liberen íntegramente los descriptores de ventanas y recursos gráficos del sistema operativo.

---

## 4. Gobernanza Regulatoria y Atomicidad Transaccional (MRM / IFRS 9)

### 4.1 Principio de Atomicidad en Cortes Manuales
En instituciones financieras reguladas bajo los estándares **SR 11-7** y **IFRS 9**, cualquier intervención humana sobre un modelo de corte objetivo (árbol de decisión) representa una excepción de gobernanza de modelos (Model Exception / Management Override).

El sistema garantiza que la instrucción de partición sobre el backend sea **estrictamente atómica**: la operación se compromete (*commit*) en el motor o se descarta íntegramente (*rollback* nulo), sin estados intermedios.

### 4.2 Protocolo de Dos Fases y Condición de Guarda Estricta
El flujo de división manual asistida en `_on_force_split(node_id)` implementa el siguiente protocolo:

```
[Usuario solicita corte manual]
               │
               ▼
[Fase 1: CandidateSplitDialog] ────(Cancelado)────► [Transacción Abortada (Sin cambios)]
               │
          (Aceptado)
               │
               ▼
      ¿Modo MRM Activo?
        │             │
       (Sí)          (No) ────────────────────────► [Partición Estándar: apply_candidate_split]
        │
        ▼
[Fase 2: MRMExceptionDialog]
        │
   ¿mrm_res == Accepted  AND  len(justification.strip()) > 5?
        │                                  │
       (Sí)                               (No)
        │                                  │
        ▼                                  ▼
[Transacción Aprobada]             [Transacción ANULADA]
  • apply_candidate_split             • Árbol intacto (is_frozen no cambia)
    (force_freeze=True)               • Sin entrada en Bitácora
  • log_entry (Bitácora Auditoría)    • Notificación en Barra de Estado
  • Sincronización de Vistas
```

### 4.3 Especificación de la Condición de Guarda en Código:
```python
if self._mrm_mode:
    mrm_dlg = MRMExceptionDialog(node_id, selected_cand, parent=self)
    mrm_res = mrm_dlg.exec()
    justification = mrm_dlg.get_justification().strip()

    # Condición de guarda estricta:
    if mrm_res != QDialog.DialogCode.Accepted or len(justification) <= 5:
        self.status_bar.showMessage(
            f"Transacción ANULADA: Excepción MRM no autorizada en nodo {node_id} "
            f"(diálogo cancelado o justificación insuficiente)."
        )
        return

    # Invocación segura al motor analítico
    ok, msg = self._tree.apply_candidate_split(node_id, selected_cand, force_freeze=True)
    if ok:
        self.audit_trail_panel.log_entry(...)
```

### 4.4 Inmutabilidad y Congelamiento de Nodos Intervenidos
Al ejecutarse una partición autorizada bajo el modo MRM:
- El nodo adquiere el estado `is_frozen = True`. Esto impide que re-entrenamientos o podas automáticas sobreescriban la decisión humana auditada.
- Los metadatos de la partición (`gini_gain`, `ks_local`, `woe`, `iv_partial`, `odds`, `justification`, timestamp de usuario) quedan registrados de forma inmutable en el componente `AuditTrailWidget`.

---

## 5. Contrato de API y Compatibilidad de Métodos de Backend

Para asegurar la estabilidad del sistema, las llamadas del frontend respetan los tipos de retorno documentados del motor analítico:

| Método del Backend | Firma / Retorno | Tratamiento en Frontend v2 |
|---|---|---|
| `DecisionTree.prune_node(node_id)` | Retorna `bool` | Asignación directa: `success = self._tree.prune_node(node_id)`. Se valida éxito sin desempaquetar tuplas. |
| `DecisionTree.apply_candidate_split(node_id, cand, force_freeze)` | Retorna `tuple[bool, str]` | Desempaquetado: `ok, msg = self._tree.apply_candidate_split(...)`. |
| `DecisionTree.get_candidate_splits(node_id)` | Retorna `list[CandidateSplit]` | Inyección en `CandidateSplitDialog` para evaluación multi-criterio. |
| `DecisionTree.export_rules(...)` | Vía `rule_exporter.py` | Exportación dual a scripts Python independientes y sentencias SQL `CASE WHEN`. |

---

## 6. Procedimiento de Validación y Arranque

Al inicializar una nueva sesión de desarrollo o validación:
1. Verificar que el entorno virtual `.venv` contenga `PySide6`, `pandas`, `numpy`, `scipy`.
2. Consultar rigurosamente este documento técnico y los manuales en `/docs` conforme a las directrices de `.antigravityrules`.
3. Ejecutar la suite de pruebas no destructivas antes de cualquier despliegue operativo.
