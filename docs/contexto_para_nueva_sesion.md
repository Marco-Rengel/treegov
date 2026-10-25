# Contexto para Nueva Sesión — TreeGov

**Fecha de última actualización:** 24/10/2026
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
| 3.6.e | Modo no-bancario | ⏳ |
| 3.7 | Cierre Fase 3 + v1.0.0rc1 | ✅ |
| 3.8 | Corrección de la atribución regulatoria (BCBS CRE 32.4) | ✅ |
| 3.9 | Poda Interactiva y Ponderada (backend, Session y GUI) | ✅ |
| **3.10.a** | Rediseño Visual UI (H3, H4, H5, H7, H8) - Toolbar, nodos HTML, panel QGroupBox, tema oscuro | ✅ |

**Suite de tests:** 452/452 PASSED

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
- **OpenCode 1.19.0** — **herramienta activa** desde el 09/10/2026.
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
  modelo de *fallback* carísimo (causa raíz de la anomalía de consumo,
  ver `docs/audit_log.md` 10/10/2026).
  **Plugin de caché:** `@jimmyyen/opencode-context-cache` instalado y
  activo (estabiliza la *cache key* de Moonshot).
  **Nota:** Kimi Code CLI 2.1.1 se probó como alternativa, pero su
  inyección de metadatos dinámicos rompe el *prefix matching* de la
  caché. OpenCode se mantiene como herramienta principal.
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
| **KS/AUC/Gini del gains table no ponderados en 3.2.g** | Decisión diferida explícita. Documentado en design_decisions.md §13.7. |
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

**Última versión publicada:** `treegov 1.0.0rc4` en PyPI (20/10/2026).
URL: https://pypi.org/project/treegov/1.0.0rc4/

**Tags de git:** v1.0.0a1, v1.0.0a2, v1.0.0a3, v1.0.0a4, v1.0.0a5, v1.0.0a6, v1.0.0rc1, v1.0.0rc2 y v1.0.0rc4 verificados el 21/10/2026 con `git show-ref --tags`. El tag v1.0.0rc3 no existe (consistente con el audit_log: rc3 quedó quemada por conflicto de inmutabilidad en PyPI).

**Protocolo PyPI (Actualizado 20/10/2026).** PyPI congela el README en el momento
del upload. Si el README del repositorio cambia después de una
publicación, la página pública queda desincronizada hasta la
próxima release. Al modificar el README, decidir explícitamente:
(a) publicar una nueva versión inmediatamente, o (b) esperar a la
próxima release con cambios de código. Nunca dejar la decisión
implícita. *(Actualización 20/10/2026)*: Para evitar inflación de versiones, los cambios puramente cosméticos (fechas, typos, diagramas) NO disparan una nueva release en PyPI; se difieren a la próxima release material y se documentan en `roadmap.md`.

Contenido del paquete: `backend_v3` (capa analítica) + `frontend_v3` (GUI
PySide6). Verificación de instalación limpia completada.

La espera decidida el 16/10/2026 quedó cerrada definitivamente. Tras la
publicación de `1.0.0rc1`, la corrección regulatoria de la Fase 3.8 y el
cierre de la Fase 3.9, la versión actual es `1.0.0rc4` (rc3 quedó
quemada por un conflicto de inmutabilidad en PyPI: se subió solo con
los cambios de D13). El README de PyPI está sincronizado con el
repo, reflejando 438/438 tests. Ver docs/roadmap.md, protocolo PyPI.

## Próximos pasos (Fase 3.11 — Rediseño Interactivo y Topología Visual)

> **Estado intermedio (mañana).** Cerrados los tres cosméticos del ReportsPanel diferidos a H4 (suite 411 → 416). Resuelto el pendiente Aider/build/twine instalado en el .venv del proyecto. Sin cambios de código analítico. Próximo paso: diseño de Fase 3.6 (validación con *datasets* públicos: German Credit, UCI).

> **Estado intermedio (tarde).** Cerrada la sub-fase 3.6.a (diseño del plan de validación con *datasets* públicos). El documento `docs/3.6_design_public_datasets.md` (811 líneas) define nueve decisiones D1-D9 aprobadas por el autor. Próximo paso: sub-fase 3.6.b (script de descarga `scripts/fetch_datasets.py` + *fixtures* versionadas `tests/fixtures/uci/`).

**Fase 3.5 — Reportes adaptados multiclase + ponderados: Cerrada
15/10/2026.** Las cuatro sub-fases (a-d) cierran el pipeline completo
de validación, reporte y monitoreo a targets multiclase (K ≥ 2) con
composición ponderada. Invariante K=2 bit a bit preservado. Suite
416/416. Commits de la familia: 56748c9, 18bbdf0, 067b33a, 580d5fa,
9af51c9, ef3de7c, 70460f6, 5658067, más el commit del cierre
documental.

**Fase 3.7 cerrada (18/10/2026).** Las sub-fases 3.7.a (auditoría de seguridad), 3.7.b (simetrización KS por pares), 3.7.c (min_child_weight expuesto), 3.7.d (tests UCI ampliados) y 3.7.e (correcciones pre-release H1, H2, pd_floor K=2) están cerradas. Suite: 434/434.

**Próximo paso inmediato (20/10/2026):** La Fase 3.9 (Poda Interactiva y Ponderada) está cerrada: backend, `Session.get_prune_sequence()` y GUI `PruneDialog` implementados y testeados. Siguiente paso: recogida de feedback para la `1.0.0` estable.

**Próximo paso inmediato (24/10/2026):** la **Fase 3.11.b (Tree Map y
Data Viewer)** en el panel izquierdo. La 3.11.a (Rediseño Base: Tema
Colab, Layout Excel, Wizard redimensionado, Nodos HTML, HUD acotado) y
la **3.11.a.1 (Hotfix Visual: layout clásico de 8 menús, toolbar
compacta IconOnly, panel izquierdo de 3 bloques, pestañas inferiores
estilo Excel, nodos QPainter "hoja de auditoría", tema oscuro forzado
vía QPalette, aristas con cortes numéricos, copia TSV Ctrl+C en tablas)
quedaron cerradas el 24/10/2026 con suite 449/449**; los mini-cierres
del 25/10/2026 (resolución de zonas grises C1 con 2 tests nuevos de
routing por `bin_edges`, blindaje Clean Room + terminología "Nodo
terminal", y copiado TSV en el `PruneDialog` con 1 test nuevo)
elevaron la suite a **452/452**. El sistema de
diseño visual quedó estandarizado en `docs/3.11_gui_design_system.md`
(normativo as-built; las sub-fases 3.11.b-d se implementan contra él).
El código de la 3.11.a.1 está commiteado (`d8194dc`); los dos bloques
posteriores del día (Ctrl+C TSV + Design System + este cierre
documental) están en el working tree pendientes de commit —verificar
con `git status` antes de editar. Los archivos de diseño de las fases
recientes quedaron alineados el 24/10/2026:
`docs/3.10.a_design_ux_ui_redesign.md` (antes `3.10_design_ux_redesign.md`),
`docs/3.10.b_design_chaid_binning.md` (antes `3.10.b_design_chaid_continuous.md`)
y `docs/3.11.a_design_colab_theme.md` (nuevo, as-built). Después de
3.11.b siguen 3.11.c (Árboles Univariados y Matriz de Costos) y 3.11.d
(Menú Contextual e Interactividad). En paralelo sigue la recogida de
feedback de `1.0.0rc4` durante 2-4 semanas; si no aparecen bugs
críticos, publicación de `1.0.0` estable. (La deuda de tags `a1`–`a6`
quedó RESUELTA el 21/10/2026: los tags existen y apuntan a commits
válidos —verificado con `git show-ref --tags`; ver la sección "Tags de
git" de este mismo documento.) Fase 3.6.e (modo no-bancario
extensivo) va en 1.1.0 o posterior.

**Fase 3.4 — CRT y QUEST multiclase: Cerrada 12/10/2026.** 2 sub-fases
(a: C&RT; b: QUEST). Ningún motor bloquea ya K > 2 en `Session.train`.
Etapa 1 QUEST con F-test de K grupos y tie-breaker Brown-Forsythe de K
grupos; Etapa 2 con QDA para K=2 (paridad) y barrido de Gini para K>2.
Los bloqueos downstream (validation, reporting, stability) siguen
activos hasta Fase 3.5. Suite 384/384. Ver `docs/roadmap.md` sección
"Desglose de la Fase 3.4" y `docs/audit_log.md` entradas del 12/10/2026
(3.4.a y 3.4.b).

**Fase 3.2 — Ponderación por muestra: Cerrada 10/10/2026.** 8 sub-fases
(a-h). Invariante C1: sin pesos, comportamiento idéntico al pre-3.2.
Suite 346/346. Ver `docs/roadmap.md` sección "Desglose de la Fase 3.2"
y `docs/audit_log.md` entradas del 10/10/2026 (3.2.a a 3.2.h) para el
detalle del alcance.

**Fase 3.3 — Categorías de población: Cerrada 11/10/2026.** 5 sub-fases
(a-e). Invariante C1: sin `population_col`, comportamiento idéntico al
pre-3.3. Suite 384/384. Ver `docs/roadmap.md` sección "Desglose de la
Fase 3.3" y `docs/audit_log.md` entrada del 11/10/2026 para el detalle.

**Deudas diferidas:**
- Fixture de tests E2E con señal real (el `_make_csv` actual genera
  target aleatorio respecto a los predictores; los E2E verifican
  *plumbing*, no analítica). Documentado en `docs/roadmap.md` sección
  "Deferred (no blocking current work)".
- Fase 2.4.e — *screenshot* automatizado de la GUI.
- Fase 2.1.b — CV scheme + *guardrail* runtime de imports backend.
- Fase 3.10.b (Cortes candidatos en panel inferior, requiere backend). Ver `docs/roadmap.md`.

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