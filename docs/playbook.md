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
