# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 10/10/2026
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

## Regla de oro del proyecto

Cada sub-fase cerrada dispara una actualización documental en el MISMO
bloque de trabajo: `docs/audit_log.md` (entrada consolidada),
`docs/roadmap.md` (estado), `docs/estado_proyecto.md` (suite real y
próximo paso), y los documentos de contexto
(`contexto_para_nueva_sesion`, `prompt_para_asistente`). Nunca se
aplaza a una sesión aparte. Aplazar la documentación desincroniza los
documentos de contexto respecto al código real y fuerza
reconstrucciones costosas al abrir un chat nuevo. Excepciones:
504/timeout del proveedor de IA (se documenta al volver), o cambio
trivial de 1 línea consolidado en la entrada de bloque.

## Regla de oro de la caché de Moonshot

La caché de prompt de Moonshot es automática y no requiere
configuración en la cuenta. Solo se activa si se cumplen tres
condiciones simultáneas: (a) el prefijo de la petición es idéntico al
de la petición anterior (mismo system prompt, mismo repo-map, mismos
archivos leídos), (b) el prefijo tiene al menos 256 tokens, (c) la
petición llega dentro del TTL, que por defecto es de 5 minutos.
Verificado empíricamente el 10/10/2026: tres tareas consecutivas
costaron $0.113, $0.155 y $0.000. Las dos primeras tuvieron pausas
largas (>5 min) y expiraron la caché. La tercera fue inmediata y se
facturó a $0.00. Consecuencia operativa obligatoria: mantener la
sesión de OpenCode abierta durante toda la jornada y hacer las tareas
en ráfagas cortas (menos de 5 minutos entre una tarea y la
siguiente). Si hay que hacer una pausa larga, la siguiente tarea paga
el prefijo completo. La regla es no verificar en PowerShell entre
cada tarea, sino acumular varias tareas y verificar en bloque al
final.

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
| 3.1.a | TreeNode/TreeModel tuple fields + TreeBuilder.target_class | ✅ (04/10/2026) |
| 3.1.b | Jeffreys multivariante + floor renormalizado + reordenamiento | ✅ (integrado en 3.1.a) |
| 3.1.c | Session.fix_spec + SessionState + bloqueo C&RT/QUEST | ✅ (05/10/2026) |
| 3.1.d | predict_pd 2D + bloqueos en validation/reporting/stability | ✅ (09/10/2026) |
| 3.1.e | Wizard multiclase: tabla de clases + warning minoritaria | ✅ (09/10/2026) |
| 3.1.f | MetricsPanel: badge Gini negativo + botón de reversión | ✅ (09/10/2026) |
| **3.1** | **Multiclase (fase completa)** | **✅ Cerrada 09/10/2026** |
| 3.2 | Ponderación por muestra | ⏳ Próxima |
| 3.3 | Categorías Indet/Insufficient/No Perf | ⏳ |
| 3.4 | CRT/QUEST multiclase | ⏳ |
| 3.5 | Reportes adaptados (multiclase + ponderación) | ⏳ |
| 3.6 | Validación con datasets públicos | ⏳ |
| 3.6.b | Modo no-bancario | ⏳ |
| 3.7 | Cierre Fase 3 + v1.0.0 | ⏳ |

**Suite de tests:** 243/243 PASSED

## Entorno de desarrollo

### Plataforma

- **Principal:** Windows nativo con Python 3.11.9 (`.venv/`). Verificado 04/10/2026: 210/210 tests.
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
- **OpenCode 1.18.35** — **herramienta activa** desde el 09/10/2026.
  Cliente de desarrollo con Kimi K3. Instalación global vía `npm`.
  Autenticación: `opencode auth login` con provider `Moonshot AI`
  (internacional, endpoint `https://api.moonshot.ai/v1`, key propia
  de Moonshot; sin la capa intermedia de NVIDIA NIM).
  Configuración de proyecto: `opencode.json` en la raíz (versionado).
  Nivel de razonamiento: `high` por defecto (`max` reservado para
  tareas complejas).
  **Modelo configurado:** `moonshotai/kimi-k3` (con la "ai" al final)
  en los campos `model` y `small_model` de `opencode.json`. Antes
  decía `moonshot/kimi-k3` y eso hacía que OpenCode cayera a un
  modelo de fallback carísimo (causa raíz de la anomalía de consumo,
  ver `docs/audit_log.md` 10/10/2026).
  **Plugin de caché:** `@jimmyyen/opencode-context-cache` instalado y
  activo (estabiliza la cache key de Moonshot).
  **Nota:** Kimi Code CLI 2.1.1 se probó como alternativa, pero su
  inyección de metadatos dinámicos rompe el prefix matching de la
  caché. OpenCode se mantiene como herramienta principal.
- **Aider 0.86.2** — **herramienta de respaldo** desde el 09/10/2026.
- **Aider 0.86.2** (histórico: reemplazó a OpenCode el 27/09/2026 y a
  NVIDIA NIM el 03/10/2026; desde el 09/10/2026 es respaldo, ver arriba).
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

### Configuración de OpenCode

- **API key:** configurada vía `opencode auth login`. Se guarda en
  `~/.local/share/opencode/auth.json`. No vive en variable de
  entorno.
- **Costes:** $3/M input, $15/M output.
- **Configuración de proyecto:** `opencode.json` (versionado).
- **Flags clave:** `autoupdate: false`, `share: "disabled"`.
  (`setCacheKey` se eliminó el 10/10/2026: era un no-op en OpenCode
  1.18.35, bug PR #51956.)

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
| **PowerShell muestra mal UTF-8 en consola** | Al verificar archivos con caracteres no-ASCII (`—`, acentos, `§`, `≥`), `git diff` en PowerShell muestra caracteres corruptos aunque el archivo esté bien. Solución: verificar en VS Code, o redirigir el diff a archivo con `Out-File -Encoding utf8` antes de leerlo. |
| **OpenCode no soporta caché explícita en V1** | El plugin `oc-plugin-caching` requiere un fork; la V1 estándar solo tiene caché implícita vía `setCacheKey: true`. Ver `audit_log.md` 09/10/2026. |
| **Documentación de cierre aplazada** | Regla de oro desde 09/10/2026: la documentación de cierre de sub-fase se hace en el mismo bloque de trabajo (roadmap + estado_proyecto + contexto + audit_log), nunca en sesión aparte. Excepciones: 504 del proveedor de IA, o cambio trivial de 1 línea consolidado en la entrada de bloque. Ver `docs/roadmap.md` "Recorded architectural decisions: Phase closure documentation: never deferred". |
| **Consumo excesivo de tokens en OpenCode/Kimi Code CLI/Aider** | Causa raíz el 10/10/2026: modelo mal escrito (`moonshot` en lugar de `moonshotai`) + plugins fantasma + TTL de caché expirado por pausas largas. Ver `docs/roadmap.md` subsección RESOLVED. Regla: mantener sesión viva, trabajar en ráfagas. |
| **El cliente Kimi Code CLI 2.1.1 consume más que OpenCode** | El cliente oficial inyecta metadatos dinámicos (paths absolutos, timestamps, telemetría) que rompen el prefix matching. OpenCode con el plugin `@jimmyyen/opencode-context-cache` sí activa la caché. Kimi Code CLI queda como alternativa puntual, no principal. |

## Cómo retomar el trabajo

### Flujo con OpenCode (herramienta activa)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    opencode

La autenticación con Moonshot AI ya está configurada
(`~/.local/share/opencode/auth.json`). No requiere variables de
entorno. Verificar que el modelo es Kimi K3 y el nivel es `high`.

### Flujo con Aider (respaldo)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    $key = Read-Host "Pega tu Moonshot API key" -AsSecureString
    $env:MOONSHOT_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
    Remove-Variable key
    aider

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

## Próximos pasos (Fase 3.2 — Ponderación por muestra)

**Fase 3.1 — Multiclase: ✅ Cerrada 09/10/2026** (6 sub-fases a-f,
suite 243/243). Ver `docs/roadmap.md` sección "Phase 3.1" para el
detalle del alcance.

**Fase 3.2 — Ponderación por muestra (próxima).**

Qué es: soporte de pesos por muestra (frecuencia o importancia) de forma
transversal al backend, para trabajar con muestras sesgadas de buró
donde la población se reajusta por pesos en lugar de disponer del
dataset completo.

Sub-fases previstas (a detallar en el diseño de la fase):

| Sub-fase | Alcance (previsto) | Estado |
|---|---|---|
| 3.2.a | Diseño estructural (dónde entran los pesos: splitting, impurezas, counts de nodo) | ⏳ |
| 3.2.b | Motores (CHAID/CRT/QUEST) con counts ponderados | ⏳ |
| 3.2.c | Session + TreeBuilder transversales | ⏳ |
| 3.2.d | Métricas y estabilidad ponderadas | ⏳ |
| 3.2.e | Wizard/GUI + tests E2E | ⏳ |

**Deudas diferidas:**
- Fixture de tests E2E con señal real (el `_make_csv` actual genera
  target aleatorio respecto a los predictores; los E2E verifican
  plumbing, no analítica). Documentado en `docs/roadmap.md` sección
  "Deferred (no blocking current work)".
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