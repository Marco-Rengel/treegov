# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 26/09/2026
**Propósito:** Este documento permite a una IA nueva (o a un colaborador) entender el estado de TreeGov en menos de 5 minutos, sin reconstruir contexto desde cero.

## Lectura obligatoria (en orden)

1. `AGENTS.md` — Instrucciones operativas para agentes IA
2. `.treegovrules` — Reglas de gobernanza y filosofía
3. `docs/estado_proyecto.md` — Dossier completo del proyecto
4. `docs/methodology.md` — Metodología matemática con citas
5. `docs/audit_log.md` — Bitácora cronológica (leer últimas 3 entradas)
6. `docs/roadmap.md` — Plan de fases

## Estado actual del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Núcleo algorítmico (4 motores + statistics + imputación) | ✅ |
| 1 | Flujo transaccional (splitting, profiling, tree_builder, session_state) | ✅ |
| 1.2 | Evaluación OOS + poda coste-complejidad | ✅ |
| 1.3 | Validación OOT + monitoreo PSI/CSI | ✅ |
| 2.0 | GUI PySide6 (esqueleto) | ✅ |
| 2.1 | Wizard transaccional + Governance Mode | ✅ |
| 2.2 | Visor interactivo de árbol | ✅ Cerrada 25/09/2026 |
| 2.3 | Panel de métricas OOS/OOT | ⏳ Próxima |
| 2.4 | Reportes + integración | ⏳ Pendiente |
| 3+ | MCP, batch scoring, IFRS 9 | ⏳ Planificadas |

**Suite de tests:** 158/158 PASSED

## Entorno de desarrollo

### Plataforma

- WSL2 (Ubuntu) con Python 3.14.4
- Windows nativo NO se usa para el proyecto (bloquea DLLs de scipy por Control de Aplicaciones)
- Entorno virtual: `.venv_linux/` (NO confundir con `.venv/`, que es de Windows)

### Herramientas

- VS Code conectado a WSL (extensión oficial de Microsoft)
- Windows Terminal con Ubuntu por defecto
- OpenCode 1.18.32 instalado en WSL con Kimi K3 vía NVIDIA NIM

### Configuración de OpenCode

- `~/.config/opencode/opencode.jsonc` (global):
  - `instructions`: AGENTS.md + .treegovrules
  - `model`: nvidia/moonshotai/kimi-k3
  - `permission`: git push/commit = ask, rm -rf = deny
- `.opencode/opencode.json` (local del proyecto):
  - `plugin`: opencode-supermemory + opencode-auto-resume
- `.opencode/` está en `.gitignore`

## Problemas conocidos y soluciones

| Problema | Solución |
|---|---|
| **Variant de OpenCode** | Default = `max` (para diseño y auditoría). Para implementación/edición: `/variants` → `high`. Para tareas triviales: `/variants` → `low`. No persiste en `opencode.jsonc` (verificado). |
| Langfuse plugin sin credenciales | Descartado (no aporta valor sin cuenta externa) |
| `Ctrl+P` no funciona en VS Code (interceptado) | Usar Windows Terminal para menús de OpenCode |
| Al pegar en terminal, a veces se cuela `~` | Escribir comandos cortos a mano |
| Al pegar en nano, el contenido se duplica | Usar Python para escribir archivos, o VS Code directo |

## Cómo retomar el trabajo

### Abrir el entorno

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate

### Ejecutar tests

    python -m pytest tests -q

### Abrir OpenCode

    opencode

Al inicio de OpenCode: presionar `/variants` → `high` (si no está en high).

### Abrir VS Code en WSL

    code .

## Próximos pasos (Fase 2.3)

**Objetivo:** Panel visual de métricas OOS/OOT.

**Funcionalidades:**

- Gini, KS, HL, Brier, ROC + AUC, PR-AUC (backend en `backend_v3/validation.py`)
- PSI, CSI, Gini Drop con semáforos Basilea/EBA (backend en `backend_v3/stability.py`)
- Mnemonics de teclado ("&") para menús

**Ideas del experto a evaluar (Fase 2.3 o 2.4):**

- Restricciones de monotonía para variables continuas/ordinales
- Exportación de reglas en formato legible (Markdown/JSON)
- Documentación automática del modelo (ficha técnica)

**Metodología:** Diseñar → Auditar diseño → Implementar → Testear → Documentar en audit_log.md.

## Documentos históricos

La carpeta `archive/` contiene documentos del proyecto anterior (DecisionTree_Modeler). Se conservan como referencia pero NO se deben citar ni usar como base para TreeGov. No contienen referencias a software privativo activo.

## Convenciones del proyecto

- **Comentarios y docs:** español para docs internos, inglés para código.
- **Tests:** valores verificados a mano, no autoreferencias.
- **Cada cambio de código:** actualizar `docs/audit_log.md`.
- **Cada fase cerrada:** actualizar `docs/roadmap.md` y `docs/estado_proyecto.md`.
- **Cero referencias a software privativo** (SPSS, Answer Tree, Stata, SAS) en docs activos.
