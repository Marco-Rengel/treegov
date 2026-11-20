# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 20/11/2026
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

**Checklist ampliado (20/10/2026).** Al cerrar una sub-fase se actualizan 8 documentos: `audit_log`, `roadmap`, `estado_proyecto`, `contexto_para_nueva_sesion`, `prompt_para_asistente`, `README.md` / `README.es.md` (cuentan como uno), `docs/api.md` y `docs/design_decisions.md` (si el cambio introdujo un nuevo default o alteró un contrato de API). Ver `AGENTS.md` sección "Documentación obligatoria".

## Regla de oro de la caché de Moonshot (refinada el 10/10/2026)

La caché de prompt de Moonshot es automática. Solo se activa si se
cumplen tres condiciones: el prefijo de la petición es idéntico al de
la petición anterior, el prefijo tiene al menos 256 tokens, y la
petición llega dentro del TTL de cinco minutos por defecto. Verificado
empíricamente el 10/10/2026: tres tareas consecutivas costaron once
punto tres, quince punto cinco y cero centavos. Las dos primeras
tuvieron pausas largas (más de cinco minutos) y expiraron la caché.
La tercera fue inmediata y se facturó a cero.

Regla operativa refinada el 10/10/2026 (tarde), tras el análisis del
bloque de la Fase 3.2. La regla anterior ("no cerrar OpenCode nunca,
mantener siempre la misma sesión") se refina a **"cerrar en fronteras
naturales"**. Dentro de una sub-fase: mantener OpenCode abierto; los
prompts de código, tests y documentación de la misma sub-fase van
seguidos, sin cerrar. Al cerrar una sub-fase (commit pusheado): cerrar
OpenCode. Al reabrir, el prefijo vuelve a ser pequeño (entre cinco y
quince mil tokens) y no arrastra el contexto acumulado de sub-fases
anteriores. El cierre documental de una fase se trata como una unidad:
los prompts de cierre van seguidos sin cerrar entre ellos. Evitar
salidas accidentales al copiar un prompt: es la palanca más simple y
más rentable.

Justificación. El bloque de la Fase 3.2 costó dieciocho dólares
treinta y cuatro centavos (Model Inference +$7.20, Context Caching
+$8.17). El ratio real de caché en el bloque fue del cincuenta y tres
por ciento. Bajo la regla anterior, el contexto acumulado crece a
doscientos mil tokens y cada tarea paga ese prefijo gigante en la
caché, además del input y output frescos. La regla refinada reduce ese
prefijo reutilizado, con un ahorro estimado del treinta por ciento.
El input y output frescos no se reducen con esta regla; requieren
prompts quirúrgicos que nombran líneas exactas y respuestas cortas,
ya que el output cuesta cinco veces el input.

Levers por orden de impacto. Primero: output del modelo (quince
dólares por millón). Segundo: input fresco (tres dólares por millón).
Tercero: prefijo cacheado. Cuarto: TTL de una hora (pendiente; ahorro
adicional estimado entre uno cincuenta y tres dólares). Análisis
completo en `docs/audit_log.md`, entrada del 10/10/2026 (tarde).

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
| 2.4.a | Diseño estructural del panel de reportes | ✅ |
| 2.4.b | Backend de reportes (GainsTable + ClassificationMatrix) | ✅ |
| 2.4.c.1 | Métodos de reporte en Session | ✅ |
| 2.4.c.2 | Panel de reportes funcional + cableado + export HTML + tests | ✅ |
| 2.4.d | Tests E2E + cierre | ✅ |
| 3.0 | Cierre de zona gris documental + 4 parámetros canónicos | ✅ |
| 3.1.a | TreeNode/TreeModel tuple fields + TreeBuilder.target_class | ✅ |
| 3.1.b | Jeffreys multivariante + floor renormalizado + reordenamiento | ✅ (integrado en 3.1.a) |
| 3.1.c | Session.fix_spec + SessionState + bloqueo C&RT/QUEST | ✅ |
| 3.1.d | predict_pd 2D + bloqueos en validation/reporting/stability | ✅ |
| 3.1.e | Wizard multiclase: tabla de clases + warning minoritaria | ✅ |
| 3.1.f | MetricsPanel: badge Gini negativo + botón de reversión | ✅ |
| **3.1** | **Multiclase (fase completa)** | **✅ Cerrada** |
| **3.2** | **Ponderación por muestra (8 sub-fases a-h)** | **✅ Cerrada** |
| **3.3** | **Categorías de población (Indet / Insufficient / No Perf)** | **✅ Cerrada** |
| **3.4** | **CRT/QUEST multiclase** | **✅ Cerrada** |
| 3.5.a | validation.py multiclase + desbloqueo K>2 | ✅ |
| 3.5.b | reporting.py multiclase + desbloqueo K>2 | ✅ |
| 3.5.c | Session multiclase (evaluate_oos, evaluate_oot, get_classification_matrix) | ✅ |
| 3.5.d | Auditoría de frontend + methodology + cierre | ✅ |
| 3.5 | Reportes adaptados (multiclase + ponderación) | ✅ Completada |
| 3.6 | Validación con datasets públicos | ✅ |
| 3.7 | Cierre Fase 3 + v1.0.0rc1 | ✅ |
| 3.8 | Corrección de la atribución regulatoria (BCBS CRE 32.4) | ✅ |
| 3.9 | Poda Interactiva y Ponderada (backend, Session y GUI) | ✅ |
| **3.10.a** | Rediseño Visual UI (H3, H4, H5, H7, H8) - Toolbar, nodos HTML, panel QGroupBox, tema oscuro | ✅ |
| **3.11.a** | Rediseño Base: Tema Colab, pestañas tipo Excel a página completa, Wizard redimensionado, nodos QPainter "hoja de auditoría" | ✅ |
| **3.11.a.1** | Hotfix Visual: layout clásico de 8 menús, toolbar IconOnly, panel izquierdo de 3 bloques, pestañas inferiores, tema oscuro forzado vía QPalette, aristas con cortes numéricos, Ctrl+C→TSV en tablas | ✅ |
| **3.11.b** | Tree Map (minimapa pasivo), Data Viewer, Project Explorer, `pct_global` en fila Total del nodo | ✅ |
| **3.11.c** | Árboles Univariados en lote + Matriz de Costos N×N | ✅ |
| **3.11.d** | Menú Contextual + Manual Override Log | ✅ |
| **3.12** | Pestañas Rules/Summary, Data Viewer por nodo y 3 curvas de ganancias; API `get_rules`/`get_summary`/`get_node_cases` | ✅ Cerrada (14/11/2026) |
| **3.6.e** | Modo No-Bancario: terminología dinámica vía `tr_term` (BANKING bit-idéntica, RESEARCH neutra) | ✅ |
| 4.0.a | Exportadores SQL y Python (`backend_v3/exporters.py`) | ✅ |
| 4.0.b | Exportador Markdown (`export_to_markdown`) | ✅ |
| 4.0.c | Integración GUI de exportadores (menú Archivo + `QFileDialog`) | ✅ |
| **4.0** | **Export to production (fase completa)** | **✅ Cerrada** |
| **4.0.1** | **Exportadores categóricos: `unseen_policy` (4.0.1.a y 4.0.1.b)** | **✅ Cerrada** |
| 5.0.a | Esqueleto headless MCP (`mcp_v3`: `_jsonable` + 24 ToolDescriptor) | ✅ |
| 5.0.b | Servidor MCP stdio + entry point (`treegov-mcp`) | ✅ |
| 5.0.c | Paridad E2E MCP + exportadores CHAID con bins fusionados (§16.4) | ✅ |
| 5.0.d | Auditoría de seguridad MCP + cierre documental as-built | ✅ |
| **5.0** | **Capa MCP (fase completa)** | **✅ Cerrada** |
| 6.0.a | Backend batch scoring + `Session.score_batch` + atomicidad anti-overwrite | ✅ |
| 6.0.b | Backend Champion-Challenger + población común + campeón inmutable | ✅ |
| 6.0.c | Diálogos GUI + workers + acciones Analysis + i18n | ✅ |
| 6.0.d | Tools MCP de scoring + hardening (26 tools totales) | ✅ |
| **6.0** | **Batch scoring y Champion-Challenger (fase completa)** | **✅ Cerrada** |
| 7.0.a | Backend IFRS 9 / ECL + `Session.calculate_ecl` | ✅ |
| 7.0.b | Diálogo GUI ECL + worker + acción Analysis + i18n | ✅ |
| 7.0.c | Tool MCP `calculate_ecl` + hardening (27 tools totales) | ✅ |
| **7.0** | **IFRS 9 / ECL (fase completa)** | **✅ Cerrada** |
| **Fase 1 Higiene** | Limpieza de repositorio (3.49 GB → 6.12 MB), entorno virtual externo limpio, `.gitignore`/`.aiderignore`, des-rastreo `archive/legacy_docs/`, anonimización `AGENTS.md` | **✅ Cerrada (20/11/2026)** |
| **Fase 2 MRM (`2A`–`2I`)** | Remediación integral de auditoría MRM `F1`: cierre **16/16** hallazgos críticos (`CRIT-01`–`CRIT-16`) + **`MEN-05`** (24 referencias simétricas, cero zonas grises), sincronización documental y preparación release **`1.0.0rc9`** | **✅ Cerrada (20/11/2026)** |

**Suite de tests:** 752/752 PASSED

## Decisiones clave recientes (§27–§33, Remediación Fase 2 — 20/11/2026)

- **§27 (Bloque 2A — `CRIT-01`, `CRIT-04`):** fuente única `validation.select_majority_leaf(model)` (máximo `n` físico, desempate por menor `node_id`); paridad exacta `SQL (SQLite) == Python == predict_pd` con identificadores ANSI SQL `"..."`, `None`/`NaN` sin imports en Python, `WHEN >` + `ELSE` en CHAID fusionado, guardas de finitud/ciclos, transparencia multiclase en exportadores y `unseen_policy` propagada en Champion-Challenger.
- **§28 (Bloque 2B — `CRIT-03`, `CRIT-05`, `CRIT-06`, `CRIT-07`):** clasificación estricta Basilea III CRE 32.4 (`BASEL_PD_FLOOR_MIN = 0.0005`, `classify_governance_mode` → `BANKING`/`RESEARCH`/`CUSTOM`, `pd_floor < 0.5`); `Session.active_tree` conectando `pruned_tree` a todos los consumidores con invalidación de métricas obsoletas; remapeo de `parent_id` en `_reindex_tree`; atomicidad de `fix_spec`/`train`/`load_oot` (exclusión de `weight_col`/`population_col`, rechazo de `NaT`) y propagación del filtro de población al `params_fingerprint`.
- **§29 (Bloque 2C — `CRIT-02`, `CRIT-15`):** conversión UI `% -> decimal` de EIR en `ECLDialog`, `eir >= 0`, `PD = 1.0` obligatorio en Etapa 3 y provisión combinada por etapa (`total_ecl_staged` / `ecl_applicable`); confinamiento MCP `TREEGOV_MCP_ROOT` solo `.csv`, bloqueo anti-sobrescritura en `score_batch`, validación fail-fast, `RLock`, `_jsonable` con normalización de claves y Caja Blanca en `treegov_mcp.py`.
- **§30 (Bloque 2D — `CRIT-08`, `CRIT-16`):** soporte multiclase $K \ge 3$ extremo a extremo (targets de texto, traducción canónica en `get_gains_table`, `ClassificationMatrix.class_labels`, resolución automática de `target_type` en `Session.train`, matriz dinámica $K \times K$ en GUI/HTML) y endurecimiento SR 11-7 de `ModelWizard` (bloqueo de `"No validar"`, resumen CV escapado, validación estricta de costos sin matriz fantasma).
- **§31 (Bloque 2E — `CRIT-09`, `CRIT-10`):** varianza ponderada de confiabilidad de Kish y raíces Citardauq en QUEST (con dominio $[\min(x), \max(x))$ y no secuestro por $F = \infty$), `bonferroni_adjust` logarítmico sin overflow, `_weighted_median` tolerante, rechazo `±inf` en `TrainOnlyImputer`/C&RT/CHAID, Gini normalizado / sumas inversas / varianza centrada (Chan, Golub & LeVeque 1983) y selección Cochran-elegible en Exhaustive CHAID.
- **§32 (Bloque 2F — `CRIT-11`, `CRIT-12`):** guardas anti-`NaN`/no-finitos en `TreeBuilder`, `splitting`, `validation` y `reporting`; `w_accuracy` binario; Hosmer-Lemeshow OOS *tie-preserving* invariante al orden con `df = G_eff` (Hosmer, Lemeshow & Sturdivant 2013 §5.2.2) y `_HL_EPS = 1e-6`; `StabilityMonitor` (`eps` conectado/validado, `leaf_psi` invariante a escala, `covariate_csi` `(a, b]` + `<MISSING>` + continuas constantes); `evaluate_oot` compatible con CV y `Gini_train <= 0` → `UNDETERMINED`.
- **§33 (Bloque 2G — `CRIT-13`, `CRIT-14`):** coherencia metodológica integral SR 11-7 (`methodology.md` incl. §5.4 Atípicos y §8.9bis, `3.10.b_design_chaid_binning.md`, `api.md`); `TreeNode.gini_impurity` con etiqueta `Impurity (I_G)`; precalculo backend en `GainsRow` y `oot["csi_worst_flag"]`; guardia Caja Blanca ampliada a 12 raíces auto-instalada; guardrail AST bidireccional de Sala Limpia (`test_frontend_clean_room` + `test_backend_clean_room`); oráculo matemático manual puro en `test_statistics.py`.

## Entorno de desarrollo

### Plataforma

- **Principal (entorno limpio externo desde Fase 1, 20/11/2026):** Windows nativo con Python 3.11.9 en `%LOCALAPPDATA%\venvs\treegov-311` (fuera del repositorio tras la limpieza de 3.49 GB → 6.12 MB). Verificado 20/11/2026: **752/752 tests PASSED**.
- **Flujo asistido vigente:** Antigravity IDE / OpenCode v2.2.5 (multi-proveedor); Aider 0.86.2 en `pipx` como respaldo documentado.
- **Respaldo:** WSL2 (Ubuntu) con Python 3.14.4 fuera del árbol del repositorio.
- **Compatibilidad declarada:** 3.11+ (ver `pyproject.toml`).

### Comandos por plataforma

Windows (PowerShell — entorno limpio externo):

    & "$env:LOCALAPPDATA\venvs\treegov-311\Scripts\python.exe" -m pytest tests -q
    & "$env:LOCALAPPDATA\venvs\treegov-311\Scripts\python.exe" treegov.py

WSL (bash):

    cd "/mnt/c/Riesgos - copia/DecisionTree_Modeler"
    source .venv_linux/bin/activate
    python -m pytest tests -q

### Herramientas

- VS Code conectado a WSL (extensión oficial de Microsoft), con terminal integrada.
- Windows Terminal con Ubuntu por defecto.
- **OpenCode v2.2.5** — **herramienta activa**. Instalación global vía `npm`. Autenticación vía `opencode auth login`. **Política multi-proveedor (01/11/2026):** modelo principal `deepseek-v4-flash-free` (OpenCode Zen, gratuito, ventana 200K), rotación `qwen3.6-plus-free` / `nemotron-3-ultra-free`, alternativa de contexto masivo Google Gemini (API Key, ~5 RPM), comodín de pago `moonshotai/kimi-k3` vía Moonshot AI directo (~$7 reservados). **Configuración:** `opencode.json` en la raíz (versionado), campos `model` y `small_model`. Cerrar la pestaña al superar el 50% de contexto para preservar cuotas y caché. **Histórico:** NVIDIA NIM → Moonshot AI directo (03/10/2026) → OpenCode Zen (01/11/2026). La combinación previa `OpenCode 1.19.0 + moonshotai/kimi-k3` operó del 09/10/2026 al 01/11/2026; sus referencias en `audit_log.md` y `roadmap.md` se conservan como registro histórico.

- **Aider 0.86.2** — herramienta de respaldo desde el 09/10/2026. Instalación global vía pipx con Python 3.11.9 (C:\Users\maren\.local\bin\aider.exe). NO instalar Aider dentro del .venv del proyecto: eso ya ocurrió el 27/09/2026 y se resolvió el 16/10/2026 (ver audit_log). Configuración local en .aider.conf.yml (no versionado). Modelo moonshot/kimi-k3 vía Moonshot AI directo.
- **build 1.6.1 / twine 7.0.0** — herramientas de empaquetado PyPI, instaladas globalmente vía pipx con Python 3.14.7. Se usan para las publicaciones de TreeGov en PyPI. NO instalar en el .venv del proyecto (regla del 16/10/2026).

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
| **Modelos discontinuados** | DeepSeek V4 Pro retirado (14/09/2026). |
| **Privacidad** | No enviar datos bancarios reales ni credenciales a APIs gratuitas. |
| **Pegado en terminal** | A veces duplica contenido o deja caracteres colgando. Escribir comandos cortos a mano. |
| `git push` desde WSL | Hacer push desde Windows nativo (PowerShell) o VS Code. |
| **Placeholder de API key** | Si pegas `$env:MOONSHOT_API_KEY = "sk-..."` literal, Aider devuelve 401. Verificar con `.Length` (~51) y `.Substring(0, 7)` sin duplicar `sk-`. |
| **Aider no aplica el edit (conversa)** | Con Moonshot, ocasionalmente Aider responde en prosa sin aplicar el cambio. Solución: prompt más directo ("TAREA: ... Aplica AHORA") o edición manual en VS Code con excepción documentada en `audit_log.md`. |
| **PowerShell muestra mal UTF-8 en consola** | Al verificar archivos con caracteres no-ASCII (`—`, acentos, `§`, `≥`), `git diff` en PowerShell muestra caracteres corruptos aunque el archivo esté bien. Solución: verificar en VS Code, o redirigir el diff a archivo con `Out-File -Encoding utf8` antes de leerlo. |
| **OpenCode no soporta caché explícita en V1** | El plugin `oc-plugin-caching` requiere un fork; la V1 estándar solo tiene caché implícita vía `setCacheKey: true`. Ver `audit_log.md` 09/10/2026. |
| **Documentación de cierre aplazada** | Regla de oro desde 09/10/2026: la documentación de cierre de sub-fase se hace en el mismo bloque de trabajo (roadmap + estado_proyecto + contexto + audit_log), nunca en sesión aparte. Excepciones: 504 del proveedor de IA, o cambio trivial de 1 línea consolidado en la entrada de bloque. Ver `docs/roadmap.md` "Recorded architectural decisions: Phase closure documentation: never deferred". |
| **Consumo excesivo de tokens en OpenCode/Kimi Code CLI/Aider** | Causa raíz el 10/10/2026: modelo mal escrito (`moonshot` en lugar de `moonshotai`) + plugins fantasma + TTL de caché expirado por pausas largas. Ver `docs/roadmap.md` subsección "OpenCode token consumption — learning from Fase 3.2 block". Regla refinada (10/10/2026 tarde): ráfaga dentro de cada sub-fase, cierre del cliente al cerrar la sub-fase; ver "Regla de oro de la caché de Moonshot" más arriba. |
| **El cliente Kimi Code CLI 2.1.1 consume más que OpenCode** | El cliente oficial inyecta metadatos dinámicos (paths absolutos, timestamps, telemetría) que rompen el prefix matching. OpenCode con el plugin `@jimmyyen/opencode-context-cache` sí activa la caché. Kimi Code CLI queda como alternativa puntual, no principal. |
| **Hosmer-Lemeshow escala con la masa total de pesos** | Comportamiento matemáticamente inevitable (χ² ponderado). Documentado en design_decisions.md §13.8. |
| **Hallazgos UX pendientes** | Ninguno. Todos los hallazgos H1–H8 fueron resueltos entre las fases 3.7.e y 3.10.a. |
| Agente se detiene o alucina por zona gris | El asistente estratégico debe buscar `# TODO(zona_gris)` en el diff. El agente debió aplicar la opción conservadora y continuar. |

## Cómo retomar el trabajo

### Flujo con OpenCode (herramienta activa)

    cd "C:\Riesgos - copia\DecisionTree_Modeler"
    .\.venv\Scripts\activate
    python -m pytest tests -q
    opencode

La autenticación con Moonshot AI ya está configurada
(`~/.local/share/opencode/auth.json`). No requiere variables de
entorno. Verificar que el modelo es Kimi K3 y el nivel es `high`.

**Regla de oro para la IA (Lecciones de la Fase 3.8):** No redactes prompts de modificación asumiendo el contenido de los archivos. El asistente (tú) ha cometido errores de anclaje y omisión de documentos (como `design_decisions.md` o `CONVENTIONS.md`). Antes de enviar una ráfaga de prompts documentales, exige al humano un `git status` y un `grep` de los valores obsoletos. Y recuerda: **todo prompt debe llevar su `[Nivel: high]` o `[Nivel: max]`**.

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

**Versión vigente del repositorio:** `treegov 1.0.0rc9` (preparada en rama `release/phase2-biblio-1.0.0rc9` el 20/11/2026 tras el saneamiento bibliográfico integral de Bloque `2I`, pendiente de merge a `main`, tag `v1.0.0rc9`, verificación de wheel y subida a PyPI por el humano).
URL objetivo: https://pypi.org/project/treegov/1.0.0rc9/

**Histórico de tags de git verificados (`git show-ref --tags`):** `v1.0.0a1` a `v1.0.0a6`, `v1.0.0rc1`, `v1.0.0rc2`, `v1.0.0rc4`, `v1.0.0rc5`, `v1.0.0rc6` (08/11/2026), `v1.0.0rc7` (14/11/2026, última subida previa en PyPI) y `v1.0.0rc8` (20/11/2026, tag histórico publicado en GitHub sobre commit `bff317c` sin subida a PyPI). El tag `v1.0.0rc3` no existe (la release `1.0.0rc3` sí está en PyPI del 21/10/2026, no yanked; el intento posterior de sobrescribirla falló por inmutabilidad y se publicó `rc4`).

**Protocolo PyPI (Actualizado 20/10/2026).** PyPI congela el README en el momento
del upload. Si el README del repositorio cambia después de una
publicación, la página pública queda desincronizada hasta la
próxima release. Al modificar el README, decidir explícitamente:
(a) publicar una nueva versión inmediatamente, o (b) esperar a la
próxima release con cambios de código. Nunca dejar la decisión
implícita. *(Actualización 20/10/2026)*: Para evitar inflación de versiones, los cambios puramente cosméticos (fechas, typos, diagramas) NO disparan una nueva release en PyPI; se difieren a la próxima release material y se documentan en `roadmap.md`. La remediación de Fase 2 (`2A`–`2I`) es un **cambio material mayor**, por lo que prepara directamente `1.0.0rc9` con paridad bibliográfica total (24 referencias + 4 regulatorias), `MEN-05` cerrado y **752/752 tests PASSED**.

Contenido del paquete: `backend_v3` (capa analítica) + `frontend_v3` (GUI PySide6 + 22 iconos SVG) + `mcp_v3` (capa MCP) + `treegov.py`/`treegov_gui.py`/`treegov_mcp.py`.

## Próximos pasos

**Fase 1 (Higiene) y Fase 2 (Remediación Integral MRM `2A`–`2I`, 16/16 `CRIT` + `MEN-05`) cerradas (20/11/2026).**
Los **16/16 hallazgos críticos (`CRIT-01`–`CRIT-16`)** más **`MEN-05`** del informe `audit_reports/F1_Informe_Ejecutivo_Final.md` están cerrados y verificados con suite **752/752 PASSED**, versión sincronizada en **`1.0.0rc9`** sobre la rama `release/phase2-biblio-1.0.0rc9`.

1. **Publicación de `1.0.0rc9` (acción humana):** revisar el diff en `release/phase2-biblio-1.0.0rc9`, hacer merge a `main`, crear tag `v1.0.0rc9`, construir el wheel (`pyproject-build`), verificar con el script `zipfile` de `AGENTS.md` los 3 archivos raíz y los 22 SVG, ejecutar `twine check` y publicar en PyPI (`twine upload`). (`v1.0.0rc8` permanece intacto como tag histórico solo en GitHub.)
2. **Fase 3 previa a `1.0.0` estable (backlog diferido):** evaluar y priorizar la deuda técnica no crítica remanente registrada en `docs/roadmap.md` (`MAY-01`–`MAY-10` y `MEN-02`–`MEN-08`, referencia `audit_reports/F1_Informe_Ejecutivo_Final.md`), junto con la revisión en pantalla real y la decisión de distribución (C1).

**Deudas diferidas históricas (registradas en `docs/roadmap.md` §Deferred):**
- Inventario `F1` Fase 3: `MAY-01`–`MAY-10` y `MEN-01`–`MEN-08` (ver tabla detallada en `docs/roadmap.md`).
- Fase 2.4.e — *screenshot* automatizado de la GUI.
- Fase 3.10.b — panel inferior de cortes candidatos (WOE/IV/Odds), requiere backend nuevo.
- Líneas surrogate punteadas en el canvas (3.11.a §7 punto 3, no implementadas en 3.11.b/d/e).
- Curvas de beneficio y ROI en Gains (diferidas de Fase 3.12 por requerir pantalla de ingresos/gastos).

**Ideas del experto (evaluar en Fase 3+):**
- Restricciones de monotonicidad.
- Exportación de reglas legibles (Markdown/JSON).
- Documentación automática del modelo.

Nota (13/10/2026): la GUI se verificó end-to-end en pantalla real el 13/10/2026. Flujo completo funcional. Hay 8 hallazgos UX diferidos en `docs/roadmap.md` que se planifican en una sub-fase posterior de rediseño.

## Documentos históricos

La carpeta `archive/` contiene documentos del proyecto anterior (DecisionTree_Modeler). Se conservan como referencia pero NO se deben citar ni usar como base para TreeGov. No contienen referencias a software privativo activo.

## Convenciones del proyecto

- **Comentarios y docs:** español para docs internos, inglés para código.
- **Tests:** valores verificados a mano, no autoreferencias.
- **Cada cambio de código:** actualizar `docs/audit_log.md`.
- **Cada fase cerrada:** actualizar `docs/roadmap.md` y `docs/estado_proyecto.md`.
- **Cero referencias a software privativo** (SPSS, Answer Tree, Stata, SAS) en docs activos.
- **Desarrollo Clean Room (regla desde 25/10/2026):** el código se deriva exclusivamente de papers académicos y estándares públicos documentados. Prohibido incluir código de terceros o lógica no trazable a una fórmula matemática explícita y auditable. Ver `docs/design_decisions.md` §0.5 y `.treegovrules` (White-box rules, punto 4).
- **i18n:** paridad estricta EN/ES, claves en snake_case.
- **Verificación manual obligatoria** tras cada tarea de Aider: `python -m pytest tests -q`, `git status`, `git diff` del archivo tocado.
