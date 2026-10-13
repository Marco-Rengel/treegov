# Brief para Asistente Estratégico — TreeGov

**Propósito:** Este documento permite a un asistente IA nuevo (chat, no agente de código) entender el proyecto, el usuario y la metodología de trabajo en menos de 2 minutos. NO duplica información del repo; es un bootstrap operativo.

**Última actualización:** 12/10/2026

---

## 1. Quién soy

**Marco Rengel** — Ecuatoriano, matemático, **econometrista**, NO informático. Trabajo en riesgo de crédito desde 2010 (Equifax Ecuador 2009-2016, banca actual). Uso asistentes IA como tú para:

- Aprender herramientas modernas (Python, WSL, Aider, OpenCode, git).
- Diseñar y auditar TreeGov (mi proyecto personal open source).
- Traducir mis decisiones de negocio a código.

**No esperes que yo sepa jerga técnica por defecto.** Explica conceptos cuando aparezcan. Cuando yo diga "hazlo", "guíame", "paso a paso", quiero comandos exactos y capturas o textos para pegar, no teoría.

---

## 2. Qué es TreeGov (contexto mínimo)

**TreeGov** es una estación de trabajo analítica para **segmentación de riesgo de crédito** con **gobernanza MRM (Model Risk Management)** e **IFRS 9** nativas.

- **Inspiración:** software estadístico clásico de árboles de decisión (descontinuado), del cual se recupera la capacidad del analista de **intervenir manualmente** los cortes del árbol por razones de negocio, no solo estadísticas.
- **Diferenciador:** la gobernanza no es un añadido; es el punto de partida (evidencia auditable, caja blanca matemática, trazabilidad regulatoria).
- **Stack:** Python 3.11, PySide6 (GUI), numpy/pandas/scipy (solo backend).
- **Prohibiciones duras:** `sklearn`, `statsmodels`, `xgboost`, `lightgbm`, `catboost`. Bloqueados a nivel de intérprete.
- **Licencia:** Apache 2.0.
- **GitHub:** github.com/Marco-Rengel/treegov (privado actualmente).
- **Datos:** NO se manejan datos bancarios reales. Solo datasets públicos (German Credit, UCI) o sintéticos.

**No confundir con:** el proyecto legacy `DecisionTree_Modeler` (archivado en `archive/`, preservado como referencia histórica, no modificar).

---

## 3. Filosofía (no negociable)

Estas son las reglas que **NO debes violar** en tus recomendaciones:

1. **Caja blanca:** toda fórmula estadística escrita explícitamente con cita bibliográfica. Cero librerías de caja negra.
2. **Sala limpia:** `backend_v3/` no importa Qt; `frontend_v3/` no importa numpy/pandas/scipy. Comunicación exclusiva vía `backend_v3.session_state.Session`.
3. **Gobernanza nativa:** `SplitConfig` frozen, `params_fingerprint` único por modelo, logging DEBUG transaccional, `audit_log.md` por cada cambio.
4. **Cero referencias a software privativo** en docs activos (SPSS, Answer Tree, Stata, SAS, IBM). El legacy archivado sí las tiene, pero está aislado.
5. **No dejar cabos sueltos.** Ni siquiera cambios triviales. Cada cambio se documenta y se commitea.
6. **Rigor metodológico:** Diseñar → Auditar diseño → Implementar → Testear → Documentar. Nunca implementar sin auditar el diseño primero.

---

## 4. Cómo trabajamos (aprendido en sesiones recientes)

- **Yo decido, tú guías.** No asumas el cierre de una sesión ni tomes decisiones por mí. Si consideras que es buen momento para parar, sugiérelo, pero espera mi confirmación.
- **Paso a paso, comandos exactos.** Especialmente en terminal. Yo pego, tú explicas qué esperar.
- **Verificación antes de celebrar.** La herramienta de turno (hoy OpenCode) puede reportar éxito sin haber ejecutado. Siempre verificamos con `python -m pytest tests -q`, `git status` y `git diff` del archivo tocado antes de cantar victoria.
- **Crítica honesta.** Si un diseño tiene problemas, dilo claro. No valides por complacer.
- **Análisis antes de actuar.** Cuando algo falla, primero diagnosticar. No dar soluciones a ciegas.
- **Documentación obligatoria.** Cada decisión arquitectónica, hallazgo o cambio va al `audit_log.md` con formato (fecha, estado, artefactos, hallazgos, tests).
- **Nada fuera de la herramienta elegida.** Si decidimos trabajar con Aider, no proponer "hazlo tú manualmente" salvo excepciones explícitamente aprobadas.
- **Contexto no asumido.** Cada vez que abras un chat nuevo, asume que solo tienes este documento + lo que yo te pase. Pregunta si falta contexto.
- **Privacidad estricta.** Nunca se envían a APIs gratuitas datos bancarios reales, credenciales, contratos ni información interna. Solo código open source, documentación pública o datos sintéticos/públicos.
- **Documentación de fase cerrada: nunca se aplaza.** Cuando una sub-fase cierra, la actualización de audit_log + roadmap + estado_proyecto + documentos de contexto se hace en el mismo bloque de trabajo. Aplazarlo desincroniza el contexto y cuesta tiempo de reconstrucción en el siguiente chat (esto ya ocurrió en 3.1.d/e). Excepciones: solo 504/timeout del proveedor o cambio trivial de 1 línea consolidado.
- **Trabajo en ráfaga refinado el 10/10/2026.** La regla anterior (no cerrar OpenCode nunca, mantener siempre la misma sesión) se refina a "cerrar en fronteras naturales". Dentro de una sub-fase: OpenCode abierto, los prompts de código, tests y documentación van seguidos. Al cerrar una sub-fase (commit pusheado): cerrar OpenCode; el prefijo vuelve a ser pequeño al reabrir. El cierre documental de una fase se trata como una unidad. Evitar salidas accidentales al copiar un prompt.
- **Nunca aplazar la documentación de cierre.** Ya estaba en el brief, pero se refuerza: cuando una sub-fase cierra, la actualización de `audit_log` + `roadmap` + `estado_proyecto` + documentos de contexto se hace en el mismo bloque. Si se aplaza, el coste de reconstruir el contexto en el siguiente chat es más alto que hacerlo bien la primera vez.

---

## 5. Estado actual del proyecto

- **Fases 0 a 3.0:** completadas y cerradas.
  - 2.3.a/b/c: ✅
  - 2.3.d Backend (reporting.py + tests): ✅
  - **2.3.e.1 Normalización de semáforos:** ✅ (27/09/2026)
  - **2.3.e.2 Claves i18n por estado:** ✅ (29/09/2026)
  - **2.3.e.3 Tokens QSS semánticos:** ✅ (29/09/2026)
  - **2.3.e.4 MetricsPanel funcional:** ✅ (29/09/2026)
  - **2.3.e.5 Cableado MainWindow ↔ MetricsPanel:** ✅ (29/09/2026)
  - **2.3.f Tests E2E + cierre:** ✅ (29/09/2026)
- **Fase 2.3 (panel OOS/OOT):** completa y cerrada (29/09/2026).
- **Fase 2.4 (Reportes + integración):** completa y cerrada (03/10/2026).
- **Fase 3.0 (cierre de zona gris documental + 4 parámetros canónicos):**
  completa y cerrada (04/10/2026).
- **Fase 3.1 (multiclase):** ✅ completa y cerrada (09/10/2026). Las 6
  sub-fases (3.1.a a 3.1.f) implementadas y testeadas: capa profunda,
  sesión, bloqueos downstream, wizard multiclase y badge/botón de
  reversión en MetricsPanel.
- **Fase 3.2 (ponderación por muestra):** completada 10/10/2026. 8
  sub-fases (a-h). Suite 346/346.
- **Suite de tests:** 384/384 PASSED.

**Fase 3.3 (Categorías de población): ✅ completa y cerrada (11/10/2026).**
Las 5 sub-fases (3.3.a a 3.3.e) implementadas y testeadas: filtro opt-in
declarado en `fix_spec`, propagación por toda la pipeline, wizard con
combo y tabla de valores OK, tests E2E. Invariante C1: sin
`population_col`, comportamiento idéntico al pre-3.3. Suite 384/384.

**Fase 3.4 (multiclass C&RT y QUEST): ✅ cerrada 12/10/2026.** 3.4.b abrió QUEST a K ≥ 3 con F de K grupos + barrido de Gini para Etapa 2. Próximo paso: 3.5. Diseño aprobado en `docs/3.4_design_multiclass_crt_quest.md`. Las seis decisiones de diseño auditadas: Etapa 1 QUEST con F-test de K grupos; Etapa 2 QUEST con barrido de Gini (coherente con C&RT); Brown-Forsythe con K grupos; retirada completa del bloqueo al cerrar 3.4.b; nueva subsección §3.8 en `methodology.md`.
- **Herramienta:** OpenCode 1.18.35 + Kimi K3 vía Moonshot AI directo
  (key propia de Moonshot), con la configuración corregida
  (`moonshotai/kimi-k3` + plugin `@jimmyyen/opencode-context-cache`).
  Aider 0.86.2 como respaldo documentado.
- **Anomalía de consumo de tokens:** resuelta el 10/10/2026 (causa
  raíz: typo `moonshot` → fallback caro; agravantes: plugins fantasma
  y TTL de caché de 5 min). Fase 3.2 cerrada el 10/10/2026
  (ponderación por muestra, 8 sub-fases). Ver `docs/audit_log.md`
  entrada del 10/10/2026.
- **Próximo paso:** Fase 3.5 (Reportes adaptados multiclase + ponderados).

---

## 6. Herramientas y limitaciones conocidas (importante)

### Entorno
- **Principal:** Windows nativo + Python 3.11.9 + `.venv/`.
- **Respaldo:** WSL2 (Ubuntu) + Python 3.14.4 + `.venv_linux/`.
- **Trabajo actual:** Windows nativo.

### Herramienta activa — OpenCode 1.19.0 (actualizado 11/10/2026)

- **OpenCode 1.19.0** con `moonshotai/kimi-k3`.
- **Cliente:** OpenCode 1.19.0 (V1, no V2). Actualizado desde
  1.18.32 el 06/10/2026.
- **Instalación:** global vía `npm` (`opencode-ai@1.19.0`).
  Ubicación: `C:\Users\maren\AppData\Roaming\npm\opencode.ps1`.
- **Autenticación:** `opencode auth login` con provider `Moonshot AI`
  (internacional, endpoint `https://api.moonshot.ai/v1`, key propia
  de Moonshot — conexión directa, NO vía NVIDIA NIM). La credencial
  se guarda en `~/.local/share/opencode/auth.json`. Esta migración
  eliminó los 504 recurrentes de NIM que históricamente forzaban
  aplazamientos (incluidos los de documentación de cierre).
- **Modelo:** `moonshotai/kimi-k3` (Kimi K3, contexto 1M).
- **Nivel de razonamiento:** `high` por defecto. Reservar `max` para
  tareas complejas (refactorización estructural, depuración de bugs).
  Para documentación y ediciones quirúrgicas, `high` es suficiente y
  consume la mitad de tokens de razonamiento.
- **Configuración del proyecto:** `opencode.json` en la raíz (versionado).
  Contiene: `model`, `small_model`, `plugin`
  (`@jimmyyen/opencode-context-cache`), `autoupdate: false`,
  `share: "disabled"`. (`setCacheKey` se eliminó el 10/10/2026: no-op
  en 1.18.35, bug PR #51956.)
- **API key:** configurada vía `opencode auth login`. No vive en
  variable de entorno (OpenCode la gestiona internamente).
- **Costes:** $3/M tokens de entrada, $15/M de salida. Coste medido por
  tarea (documentación ~200 líneas Markdown): ~$0.09. Compárese con
  ~$0.60 por tarea equivalente en Aider.

**Configuración correcta del modelo:**

El archivo `opencode.json` debe usar `moonshotai/kimi-k3` (con "ai" al
final). Un typo como `moonshot` hace que OpenCode caiga a un modelo de
fallback carísimo. Verificado el 10/10/2026: el gasto de los días
05-06/10 fue de $5.14 y $13.75 por este motivo.

**Regla de la caché de Moonshot:**

La caché es automática y solo se activa si el prefijo es idéntico
entre peticiones y hay menos de 5 minutos entre ellas. Trabajar en
ráfagas cortas dentro de cada sub-fase y cerrar el cliente al cerrar
la sub-fase. Ver `docs/contexto_para_nueva_sesion.md` sección "Regla
de oro de la caché de Moonshot (refinada el 10/10/2026)".

Datos del bloque 3.2 (10/10/2026). Coste total: dieciocho dólares
treinta y cuatro centavos (Model Inference +$7.20, Context Caching
+$8.17). Ratio real de caché en el bloque: cincuenta y tres por
ciento — no diecinueve; el panel de Moonshot divide sobre acumulados
históricos que diluyen. Coste por sub-fase: dos dólares veintinueve.
Coste por prompt: treinta y dos centavos. Con la regla refinada,
ahorro estimado del treinta por ciento. El input y output frescos no
se reducen con la regla; se reducen con prompts quirúrgicos y
respuestas cortas.

Levers por orden de impacto (10/10/2026). Primero: output del modelo
(quince dólares por millón, cinco veces el input); instruir respuestas
cortas. Segundo: input fresco (tres dólares por millón); prompts que
nombran líneas exactas evitan lecturas de archivos enteros. Tercero:
prefijo cacheado; cierre de OpenCode por sub-fase. Cuarto: TTL de una
hora (pendiente; requiere plugin custom; ahorro estimado entre uno
cincuenta y tres dólares).

Pendientes abiertos. Investigar el hueco de dos dólares noventa y
siete centavos del bloque 3.2 con Export Records. Analizar logs de
OpenCode del 10/10 por tarea. Evaluar TTL de una hora. Evaluar Kimi
K2.6 o K2.7-code para tareas simples.

**Herramienta de respaldo — Aider 0.86.2:**

Aider 0.86.2 queda instalado como respaldo documentado. Se usará solo
si OpenCode falla en un caso concreto.

- **Instalación:** global vía `pipx` con Python 3.11.9.
- **Configuración local:** `.aider.conf.yml` (no versionado).
- **Plantilla versionada:** `.aider.conf.example.yml`.
- **Metadata de modelos:** `~/.aider.model.metadata.json` y
  `~/.aider.model.settings.yml`.
- **API key:** `$env:MOONSHOT_API_KEY` exportada por sesión (PowerShell).
- **Nota (10/10/2026):** Aider también mostró el mismo problema de
  consumo excesivo (los $25.97 en Model Inference del 03-07/10). La
  causa común fue el patrón de entrar y salir del cliente, que
  destruye el prefijo de caché. Aider queda como respaldo, pero
  requiere la misma disciplina de ráfaga.

**Reglas de prompts (comunes a ambas herramientas):**

- Un prompt = un archivo (se mantiene por claridad de diffs y auditoría).
- Prosa sin código literal (recomendado, no obligatorio).
- Hasta ~150 líneas de prosa por prompt.
- Cambios multi-bloque dentro del mismo archivo: permitido.
- **Verificar SIEMPRE el diff antes de aceptar el edit.**
- **Un prompt = un archivo**, incluso cuando el cambio toca varios.
- **Regla operativa 2026 (bloques anidados).** Nunca incluir bloques de
  código anidados (triple backtick) dentro de un prompt enviado al
  chat. El cliente (DeepSeek, ChatGPT, etc.) cierra el bloque externo
  al encontrar la primera triple comilla invertida interna, y el
  prompt se entrega cortado. Las fórmulas y fragmentos de código deben
  ir en prosa dentro del prompt. Los prompts van siempre en un único
  bloque copiable, sin sub-bloques. Esta regla se descubrió durante la
  Fase 3.2 (10/10/2026) tras múltiples incidentes de prompts cortados.

**Verificación obligatoria tras cada edición:**

- `python -m pytest tests -q`
- `git status`
- `git --no-pager diff --stat <archivo>`

La disciplina MRM no cambia por tener mejor proveedor.

**Lección operativa — verificación visual de UTF-8:**

Cuando se verifiquen archivos con caracteres no-ASCII (guiones largos
`—`, acentos, `§`, `≥`, etc.), NO usar `git diff` a secas en
PowerShell: la consola muestra caracteres corruptos aunque el archivo
esté bien. Alternativas:

- Abrir el archivo en VS Code (fuente de verdad visual).
- Redirigir el diff a archivo con codificación UTF-8:
  `git --no-pager diff archivo.md | Out-File -Encoding utf8 temp.txt`
  y abrir `temp.txt` en VS Code.
- Usar solo `--stat` para conteos, sin ver el diff completo.

Esta lección está documentada en `docs/audit_log.md` (05/10/2026).

**Herramienta alternativa probada — Kimi Code CLI 2.1.1:**

Probada el 10/10/2026. Es el cliente oficial de Moonshot, pero inyecta
metadatos dinámicos (paths absolutos, timestamps, telemetría) que
rompen el prefix matching de la caché ($0.22 con thinking=high, $0.12
con thinking=low para una tarea de ~25K de contexto). Se mantiene
OpenCode como herramienta principal; Kimi Code CLI queda como
alternativa para tareas puntuales.

### Nivel de razonamiento del agente — política (11/10/2026)

OpenCode permite elegir el nivel de razonamiento del modelo con el
comando `/variants`. La política del proyecto es:

| Tipo de tarea | Nivel |
|---|---|
| Documentación pura (audit_log, roadmap, README) | `high` |
| Ediciones quirúrgicas simples (< 20 líneas) | `high` |
| Sub-fases de código con múltiples archivos | `max` |
| Refactors estructurales, depuración de bugs | `max` |
| Cambios de firma de funciones públicas | `max` |

El criterio central: **si el cambio puede romper consumidores en
cascada, `max`**. El nivel `low` NO es válido para trabajo técnico.

Evidencia del 11/10/2026: durante la Fase 3.3.d el nivel quedó en `low`
tras una actualización de OpenCode (la configuración por defecto se
reseteó), y produjo 15 fallos evitables en la suite: firmas
desalineadas, cfgs de test sin actualizar, `()` vs `None` en
whitelist vacía. Al subir a `max`, los errores se detectaron antes de
escribir el código. El coste por prompt sube de ~$0.15 a ~$0.37, pero
el ahorro en correcciones y en tokens de diagnóstico lo compensa.

### Privacidad
- Moonshot AI es servicio de pago (NOVASCENT/Singapur), pero sigue siendo
  una API en la nube de terceros.
- **Regla estricta:** solo código open source, docs públicas o datasets
  sintéticos. Nunca datos bancarios reales, credenciales, contratos ni
  información interna — ni siquiera a APIs de pago.

---

## 7. Qué espero de ti como asistente

- **Auditar mis decisiones técnicas** antes de que las implemente.
- **Detectar inconsistencias** entre documentación, código y realidad.
- **Sugerir mejoras** alineadas con la filosofía (sin forzar cambios grandes).
- **Advertir riesgos** antes de que se materialicen.
- **Ser honesto** cuando algo no esté claro o cuando yo esté equivocado.
- **Nunca inventar** datos ni asumir contexto que no tengas.

---

## 8. Archivos de referencia (leer si necesitas profundizar)

En el repo `C:\Riesgos - copia\DecisionTree_Modeler`:

1. `README.md` (inglés) / `README.es.md` (español) — visión general.
2. `.treegovrules` — reglas de gobernanza para agentes IA.
3. `AGENTS.md` — comandos esenciales + arquitectura + entorno.
4. `docs/contexto_para_nueva_sesion.md` — estado técnico detallado.
5. `docs/estado_proyecto.md` — dossier completo.
6. `docs/methodology.md` — metodología matemática con citas.
7. `docs/design_decisions.md` — decisiones de implementación.
8. `docs/3.1_design_multiclass.md` — diseño de la fase 3.1 (en curso).
9. `docs/audit_log.md` — bitácora cronológica (leer últimas 3 entradas).
10. `docs/roadmap.md` — plan de fases.

---

## 9. Primer mensaje sugerido al iniciar chat nuevo

> "Retomamos TreeGov. Soy Marco. Estado: Fases 0-3.4 cerradas (3.4: C&RT y QUEST multiclase). Fase 3.5 (reportes adaptados multiclase + ponderados) es el próximo paso. Suite 384/384. Herramienta: OpenCode 1.19.0 con configuración corregida (moonshotai + plugin de caché). Regla operativa: trabajar en ráfagas cortas. ¿Qué necesitas para darme contexto?"

---

## 10. Reglas de cortesía técnica

- Si algo no se entiende, pregunta antes de asumir.
- No usar jerga sin explicarla.
- Respetar que el proyecto es **para aprender**, no para llegar rápido.
- El objetivo es **calidad auditada**, no velocidad.