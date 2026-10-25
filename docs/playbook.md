# TreeGov — Playbook de Gobernanza y Flujos de Trabajo

**Propósito.** Este documento define los "Skills" (habilidades o flujos de trabajo obligatorios) que el asistente estratégico y el agente de código (OpenCode/Kimi) deben ejecutar para mantener la disciplina MRM. Su objetivo es evitar olvidos de documentación y asegurar que el código nunca preceda al diseño formal.

## Skill 1: `/nueva_fase` (Prevención de Saltos de Diseño)

**Regla de oro:** Ningún prompt de código (`[Nivel: max]`) puede ser redactado hasta que el archivo de diseño correspondiente (`docs/X.Y_design_*.md`) exista, esté completo y haya sido aprobado por el humano.

**Flujo obligatorio:**
1. El humano y el asistente discuten la fase.
2. El asistente redacta un prompt para crear el archivo `docs/X.Y_design_*.md` (con Contexto, Alternativas, Decisiones y Plan de Sub-fases).
3. Una vez creado el archivo, el asistente lo audita leyéndolo.
4. Solo entonces, el asistente puede empezar a generar prompts para modificar `backend_v3/` o `frontend_v3/`.

## Skill 2: `/cierre_fase` (Checklist de 8 documentos)

**Regla de oro:** Una sub-fase no se considera cerrada hasta que los 8 documentos del checklist estén sincronizados. No basta con que los tests pasen.

**Checklist obligatorio antes del commit:**
1. `docs/audit_log.md` (entrada de cierre).
2. `docs/roadmap.md` (estado actualizado).
3. `docs/estado_proyecto.md` (conteo de tests y narrativa).
4. `docs/contexto_para_nueva_sesion.md` (próximo paso).
5. `docs/prompt_para_asistente.md` (herramienta y estado).
6. `README.md` / `README.es.md` (versión y tabla de fases).
7. `docs/api.md` (si hubo cambios de API).
8. `docs/design_decisions.md` (si hubo nuevos defaults o contratos).

## Skill 3: `/auditoria_max` (Verificación Adversarial)

**Regla de oro:** Antes de asumir que un código recién escrito funciona como se pidió, el agente debe auditar su propio trabajo.

**Flujo obligatorio:**
1. El humano pide al asistente un prompt de auditoría.
2. El prompt debe llevar `[Nivel: max]`.
3. El agente (Kimi) debe revisar empíricamente (leyendo el código) que se cumplen los invariantes matemáticos y de gobernanza.
4. Si detecta fallos, los reporta y no se commitea hasta corregirlos.

## Skill 4: Registro de archivos de diseño por fase (compliance del Skill 1)

**Regla de oro:** Cada fase o sub-fase con código implementado tiene exactamente UN archivo de diseño canónico en `docs/`. La tabla siguiente es la fuente de verdad del mapeo fase → archivo; se actualiza en el mismo bloque que cierra la sub-fase (regla "Phase closure documentation: never deferred"). Si el archivo documenta el estado as-built, lleva una sección "Estado implementado (as-built)" con referencias `archivo:línea` verificadas contra el código.

| Fase | Archivo de diseño canónico | Estado |
|---|---|---|
| **3.1** | `docs/3.1_design_multiclass.md` | ✅ Completed |
| **3.2** | `docs/3.2_decisions_consolidated.md` | ✅ Completed |
| **3.3** | `docs/3.3_design_population_categories.md` | ✅ Completed |
| **3.4** | `docs/3.4_design_multiclass_crt_quest.md` | ✅ Completed |
| **3.5** | `docs/3.5_design_multiclass_weighted_reports.md` | ✅ Completed |
| **3.6** | `docs/3.6_design_public_datasets.md` | ✅ Completed |
| **3.7** | `docs/3.7_design_pre_release_fixes.md` | ✅ Completed |
| **3.8** | `docs/3.8_design_regulatory_attribution.md` | ✅ Completed |
| **3.9** | `docs/3.9_design_interactive_weighted_pruning.md` | ✅ Completed |
| **3.10.a** | `docs/3.10.a_design_ux_ui_redesign.md` | ✅ Completed (22/10/2026; as-built §5) |
| **3.10.b** | `docs/3.10.b_design_chaid_binning.md` | ✅ Completed (23/10/2026; as-built §4) |
| **3.11 (fase)** | `docs/3.11_design_interactive_tree.md` + referencia visual `docs/3.11_classic_tree_ui_reference.md` | 🟡 En progreso |
| **3.11.a** | `docs/3.11.a_design_colab_theme.md` (as-built) | ✅ Completed (24/10/2026) |
| **3.11.a.1** | Hotfix Visual (Toolbar compacta, Wizard Dark/Light, Paso 3 moderno, Nodos sin espacio vacío); especificación en `docs/3.11_classic_tree_ui_reference.md` | ✅ Completed (24/10/2026) |
| **3.11.b–d** | Pendiente de diseño propio; alcance previsto en `docs/3.11_design_interactive_tree.md` §6 | ⏳ Pendiente |

**Nota:** El estándar visual de referencia es el Estándar Clásico de Estaciones de Árboles (circa 2001). Terminología: Nodo / Nodo terminal.
