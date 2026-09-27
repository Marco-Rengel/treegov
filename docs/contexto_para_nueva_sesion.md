# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 27/09/2026
**Propósito:** Este documento permite a una IA nueva (o a un colaborador) entender el estado de TreeGov en menos de 5 minutos, sin reconstruir contexto desde cero.

## Lectura obligatoria (en orden)

1. `AGENTS.md` — Instrucciones operativas para agentes IA
2. `.treegovrules` — Reglas de gobernanza y filosofía
3. `docs/estado_proyecto.md` — Dossier completo del proyecto
4. `docs/methodology.md` — Metodología matemática con citas
5. `docs/audit_log.md` — Bitácora cronológica (leer últimas 3 entradas)
6. `docs/roadmap.md` — Plan de fases con sub-plan de 2.3
7. `docs/prompt_para_asistente.md` — Brief para asistentes IA nuevos

## Estado actual del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Núcleo algorítmico (4 motores + statistics + imputación) | ✅ |
| 1 | Flujo transaccional (splitting, profiling, tree_builder, session_state) | ✅ |
| 1.2 | Evaluación OOS + poda coste-complejidad | ✅ |
| 1.3 | Validación OOT + monitoreo PSI/CSI | ✅ |
| 2.0 | GUI PySide6 (esqueleto) | ✅ |
| 2.1 | Wizard transaccional + Governance Mode | ✅ |
| 2.2 | Visor interactivo de árbol | ✅ |
| 2.3.a | Diseño estructural panel OOS/OOT | ✅ |
| 2.3.b | 23 claves i18n (paridad EN/ES) | ✅ |
| 2.3.c | Esqueleto del panel + 3 tests | ✅ |
| 2.3.d | Backend de reporting (reporting.py + Session) | 🟡 Parcial (faltan tests) |
| 2.3.e | Semáforos y visualización | ⏳ Próxima |
| 2.3.f | Tests E2E + cierre | ⏳ |
| 2.4 | Reportes + integración | ⏳ |
| 3+ | MCP, batch scoring, IFRS 9 | ⏳ |

**Suite de tests:** 161/161 PASSED

## Entorno de desarrollo

### Plataforma

- **Principal:** Windows nativo con Python 3.11.9 (`.venv/`). Verificado 27/09/2026: 161/161 tests.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 (`.venv_linux/`).
- **Motivo del respaldo:** Windows bloqueó scipy en el pasado (WDAC/Smart App Control). Actualmente funciona sin bloqueo.
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).

### Comandos por plataforma

Windows (PowerShell):

    .\.venv\Scripts\activate
    python -m pytest tests -q
    python treegov.py

WSL (bash):

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

### Herramientas

- VS Code conectado a WSL (extensión oficial de Microsoft), con terminal integrada.
- Windows Terminal con Ubuntu por defecto.
- OpenCode 1.18.32 en Windows y WSL.
- **Proveedor principal de IA:** Gemini 3.8 Flash (Google AI Studio).
- **Segunda opinión (diseño/auditoría):** Kimi K3 (NVIDIA NIM), **sin tool calls**.

### Configuración de OpenCode

Windows: `C:\Users\maren\.config\opencode\opencode.jsonc` y `C:\Users\maren\.local\share\opencode\auth.json`.

WSL: `~/.config/opencode/opencode.jsonc` y `~/.local/share/opencode/auth.json`.

Contenido común (Windows):

- `instructions`: [".treegovrules"] (AGENTS.md se autodescubre desde la raíz del proyecto)
- `permission`: git push/commit = ask, rm -rf = deny
- Plugin local del proyecto: opencode-supermemory + opencode-auto-resume (en `.opencode/opencode.json`)

## Problemas conocidos y soluciones

| Problema | Solución |
|---|---|
| **Bug Kimi K3 + NVIDIA NIM** | Tras tool calls, no emite mensaje final y a veces reporta "Respuesta lista" sin ejecutar. **Usar Gemini 3.8 Flash para tool calls.** Ver `docs/audit_log.md` (27/09/2026). |
| **Cuota NVIDIA NIM agotada (429)** | Se agota rápido con tool calls. Gemini 3.8 Flash (Google AI Studio) es la alternativa sin este problema. |
| **Variant de OpenCode** | No persiste en `opencode.jsonc`. Ajustar con `/variants` al inicio de cada sesión. `high` por defecto; `max` solo si el proveedor lo soporta bien. |
| **Modelos descontinuados** | DeepSeek V4 Pro fue retirado (14/09/2026). Verificar vigencia antes de seleccionar. |
| **Privacidad** | No enviar a APIs gratuitas datos bancarios reales, credenciales, contratos ni información interna. El proyecto es open source y no maneja datos reales. |
| `Ctrl+P` no funciona en VS Code | Usar Windows Terminal para menús de OpenCode. |
| Al pegar en terminal, a veces se cuela `~` | Escribir comandos cortos a mano. |
| Al pegar en nano, el contenido se duplica | Usar Python para escribir archivos, o VS Code directo. |
| `git push` falla desde terminal WSL | Hacer push desde VS Code: `Ctrl+Shift+P` → `Git: Push`. |

## Cómo retomar el trabajo

### Windows (principal)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    opencode

### WSL (respaldo)

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

## Próximos pasos (Fase 2.3.e)

**Objetivo:** Semáforos y visualización de métricas OOS/OOT en el panel.

**Requisitos:**

- Consumir `traffic_light()` y `gini_drop_alert()` del backend
  (`backend_v3/stability.py`).
- Renderizar badges visuales (verde/ámbar/rojo) en `metrics_panel.py`.
- Sin importar numpy/pandas/scipy en frontend_v3 (sala limpia).
- Usar QSS del tema activo (colores semánticos).

**Proveedor recomendado:** Gemini 3.8 Flash (proveedor principal).

**Pendientes posteriores:** 2.3.d (tests de `reporting.py`),
2.3.f (tests E2E + cierre), 2.4 (reportes).

**Ideas del experto (evaluar en 2.4 o 3):**

- Restricciones de monotonía.
- Exportación de reglas legibles (Markdown/JSON).
- Documentación automática del modelo.

## Documentos históricos

La carpeta `archive/` contiene documentos del proyecto anterior (DecisionTree_Modeler). Se conservan como referencia pero NO se deben citar ni usar como base para TreeGov. No contienen referencias a software privativo activo.

## Convenciones del proyecto

- **Comentarios y docs:** español para docs internos, inglés para código.
- **Tests:** valores verificados a mano, no autoreferencias.
- **Cada cambio de código:** actualizar `docs/audit_log.md`.
- **Cada fase cerrada:** actualizar `docs/roadmap.md` y `docs/estado_proyecto.md`.
- **Cero referencias a software privativo** (SPSS, Answer Tree, Stata, SAS) en docs activos.
- **i18n:** paridad estricta EN/ES, claves en snake_case.
- **Verificación manual obligatoria** tras cada tarea de OpenCode: `Get-Item`, `Select-String`, `pytest`, `git status`.