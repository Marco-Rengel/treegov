# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 04/10/2026
**Propósito:** Este documento permite a una IA nueva (o a un colaborador) entender el estado de TreeGov en menos de 5 minutos, sin reconstruir contexto desde cero.

## Lectura obligatoria (en orden)

1. `AGENTS.md` — Instrucciones operativas para agentes IA
2. `.treegovrules` — Reglas de gobernanza y filosofía
3. `CONVENTIONS.md` — Convenciones operativas para Aider
4. `docs/estado_proyecto.md` — Dossier completo del proyecto
5. `docs/methodology.md` — Metodología matemática con citas
6. `docs/audit_log.md` — Bitácora cronológica (leer últimas 3 entradas)
7. `docs/roadmap.md` — Plan de fases
8. `docs/prompt_para_asistente.md` — Brief para asistentes IA nuevos

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
| 2.3.d | Backend de reporting (reporting.py + Session + tests) | ✅ |
| 2.3.e.1 | Normalización de semáforos (alfabeto en inglés) | ✅ |
| 2.3.e.2 | i18n: renombrar claves y añadir nuevas | ✅ |
| 2.3.e.3 | Tokens QSS semánticos | ✅ |
| 2.3.e.4 | MetricsPanel funcional | ✅ |
| 2.3.e.5 | Cableado MainWindow ↔ MetricsPanel | ✅ |
| 2.3.f | Tests E2E + cierre (Fase 2.3 completa) | ✅ |
| 2.4.a | Diseño estructural del panel de reportes | ✅ (01/10/2026) |
| 2.4.b | Backend de reportes (GainsTable + ClassificationMatrix) | ✅ (03/10/2026) |
| 2.4.c.1 | Métodos de reporte en Session | ✅ (03/10/2026) |
| 2.4.c.2 | Panel de reportes funcional + cableado + export HTML + tests | ✅ (03/10/2026) |
| 2.4.d | Tests E2E + cierre | ✅ (03/10/2026) |
| 3.0 | Cierre de zona gris documental + 4 parámetros canónicos | ✅ (04/10/2026) |
| 3.1.a | Diseño estructural multiclase (`docs/3.1_design_multiclass.md`) | ✅ (04/10/2026) |
| 3.1.b-f | Implementación multiclase (`TreeNode`/`TreeModel` + wizard + panel) | ⏳ Próxima |
| 3.2 | Ponderación por muestra | ⏳ |
| 3.3 | Categorías Indet/Insufficient/No Perf | ⏳ |
| 3.4 | CRT/QUEST multiclase | ⏳ |
| 3.5 | Reportes adaptados (multiclase + ponderación) | ⏳ |
| 3.6 | Validación con datasets públicos | ⏳ |
| 3.6.b | Modo no-bancario | ⏳ |
| 3.7 | Cierre Fase 3 + v1.0.0 | ⏳ |

**Suite de tests:** 206/206 PASSED

## Entorno de desarrollo

### Plataforma

- **Principal:** Windows nativo con Python 3.11.9 (`.venv/`). Verificado 04/10/2026: 206/206 tests.
- **Librerías:** numpy 1.26.4, scipy 1.15.3, pandas 3.0.6, PySide6 6.11.2 (degradadas por instalación de Aider; ver audit_log 27/09/2026).
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
- **Aider 0.86.2** (reemplaza a OpenCode desde el 27/09/2026 y a NVIDIA NIM
  desde el 03/10/2026).
- **Modelo:** `moonshot/kimi-k3` (Moonshot AI directo, plataforma internacional).
- **Endpoint:** `https://api.moonshot.ai/v1` (LiteLLM lo conoce por defecto).
- **Configuración local:** `.aider.conf.yml` (no versionado).
- **Metadata de modelos:**
  - `~/.aider.model.metadata.json` — contexto y costes.
  - `~/.aider.model.settings.yml` — comportamiento (temperature, edit format).

### Configuración de Aider

- **API key:** `$env:MOONSHOT_API_KEY` exportada por sesión (PowerShell).
  Se pide de forma segura con `Read-Host -AsSecureString`.
- **Costes:** $3/M tokens input, $15/M output.
- **Configuración de proyecto:** `.aider.conf.yml` (ignorado por git).
- **Flags clave:** `auto-commits: false`, `auto-lint: false`, `auto-test: false`.

## Problemas conocidos y soluciones

| Problema | Solución |
|---|---|
| **Bug OpenCode + Gemini** | `Requests ending with a model turn are not supported` bloquea escritura tras exploración. **Migrado a Aider.** Ver `audit_log.md`. |
| **Context window de Kimi K3** | Aider no conoce el modelo; requiere `~/.aider.model.metadata.json`. Con Moonshot, además, `~/.aider.model.settings.yml` con `use_temperature: false`. Ver `audit_log.md` 03/10/2026. |
| **Kimi K3 rechaza temperature≠1** | Modelo de razonamiento. Moonshot devuelve `invalid temperature: only 1 is allowed for this model`. Solución: `use_temperature: false` en `~/.aider.model.settings.yml`. |
| **Line endings mezclados (CRLF/LF)** | Si un commit muestra cientos de líneas cambiadas en un archivo que solo recibió un bloque, es mezcla de line endings. Diagnóstico: `git diff -w --stat`. Solución: `.gitattributes` con `-text` para archivos con historial CRLF. Ver commit `7040046` y `audit_log.md` 03/10/2026. |
| **API key mal pegada** | Verificar `$env:MOONSHOT_API_KEY.Length` (~51) y que empieza con `sk-`. Si no, pedirla otra vez con `Read-Host -AsSecureString`. |
| **BOM en archivos JSON creados con PowerShell** | Usar `[System.IO.File]::WriteAllText(..., [System.Text.UTF8Encoding]::new($false))`. |
| **Modelos descontinuados** | DeepSeek V4 Pro retirado (14/09/2026). |
| **Privacidad** | No enviar datos bancarios reales ni credenciales a APIs gratuitas. |
| **Pegado en terminal** | A veces duplica contenido o deja caracteres colgando. Escribir comandos cortos a mano. |
| `git push` desde WSL | Hacer push desde Windows nativo (PowerShell) o VS Code. |
| **Placeholder de API key** | Si pegas `$env:MOONSHOT_API_KEY = "sk-..."` literal, Aider devuelve 401. Verificar con `.Length` (~51) y `.Substring(0, 7)` sin duplicar `sk-`. |
| **Aider no aplica el edit (conversa)** | Con Moonshot, ocasionalmente Aider responde en prosa sin aplicar el cambio. Solución: prompt más directo ("TAREA: ... Aplica AHORA") o edición manual en VS Code con excepción documentada en `audit_log.md`. |

## Cómo retomar el trabajo

### Windows (principal)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    $key = Read-Host "Pega tu Moonshot API key" -AsSecureString
    $env:MOONSHOT_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
    Remove-Variable key
    aider

### WSL (respaldo)

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

## Estado de release

**Última versión publicada:** `treegov 1.0.0a1` en PyPI (03/10/2026).
URL: https://pypi.org/project/treegov/1.0.0a1/

Contenido del paquete: `backend_v3` (capa analítica) + `frontend_v3` (GUI
PySide6). Verificación de instalación limpia completada.

## Próximos pasos (Fase 3.1)

**Fase 3.1 — Multiclase (en curso).**

El diseño estructural está completado (`docs/3.1_design_multiclass.md`).
La implementación está dividida en 6 sub-fases:

| Sub-fase | Alcance | Estado |
|---|---|---|
| 3.1.a | `TreeNode`/`TreeModel` tuple fields + `TreeBuilder.target_class` | 🟡 WIP — código adaptado (180/206 tests passing; 26 fallos mecánicos en 5 archivos de tests) |
| 3.1.b | Jeffreys multivariante + floor renormalizado + reordenamiento canónico | ✅ (integrado en 3.1.a) |
| 3.1.c | `Session.fix_spec` + `SessionState` + bloqueo C&RT/QUEST | ⏳ |
| 3.1.d | `predict_pd` 2D + bloqueos en validation/reporting/stability | ⏳ |
| 3.1.e | Wizard: selección obligatoria + counts + warning minoritaria | ⏳ |
| 3.1.f | MetricsPanel: badge Gini negativo + botón de reversión | ⏳ |

**Decisiones clave de Fase 3.1:**
- `pd_final`, `pd_jeffreys`, `n_events` pasan a `tuple[...]`.
- Nuevo campo `TreeNode.class_labels`.
- `target_class` y `class_labels` **obligatorios** en `Session.fix_spec`.
- Jeffreys multivariante: `(k_c + 0.5) / (n + K * 0.5)`.
- Reordenamiento canónico: clase de interés siempre en índice 0.
- Solo CHAID multiclase en 3.1 (C&RT y QUEST en 3.4).
- Métricas y reportes siguen binarios hasta 3.5.

**Deudas diferidas:**
- Fase 2.4.e — screenshot automatizado de la GUI.
- Fase 2.1.b — CV scheme + guardrail runtime de imports backend.

**Ideas del experto (evaluar en Fase 3+):**
- Restricciones de monotonicidad.
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
- **Verificación manual obligatoria** tras cada tarea de Aider: `python -m pytest tests -q`, `git status`, `git diff` del archivo tocado.