# Filosofía TreeGov

## La frase central

> «Python le da el motor. TreeGov le da el motor, el freno, el tablero, el cinturón de seguridad y el registro de mantenimiento. ¿Cuál prefiere para un modelo que va a ser auditado por el regulador?»

## ¿Por qué existe TreeGov?

Existe una generación de analistas de riesgo que necesita herramientas GUI para construir árboles auditables, y las herramientas que existían fueron discontinuadas sin reemplazo. Las librerías estadísticas y los entornos de scripting ofrecen potencia analítica, pero no gobernanza nativa. TreeGov llena ese vacío.

## El diferenciador

La gobernanza no es un añadido. Es el punto de partida:

- Configuración inmutable (*SplitConfig frozen*) = evidencia auditable.
- *Logging DEBUG* transaccional = trazabilidad regulatoria.
- Caja blanca matemática = fórmulas citables y verificables.
- Bloqueo de librerías de caja negra = auditabilidad por diseño.

## ¿A quién sirve?

- Analistas de riesgo de crédito que quieren dedicar tiempo al análisis, no a la programación.
- Equipos de validación MRM que necesitan trazabilidad completa.
- Reguladores que exigen auditabilidad de modelos de PD y clasificación.
- Científicos de datos y analistas de negocio que prefieren centrarse en la interpretación del modelo en lugar de escribir código de infraestructura.

## Compromiso

TreeGov compite en transparencia, gobernanza y defendibilidad regulatoria. La precisión predictiva sigue siendo importante, pero nunca a costa de la explicabilidad y la auditabilidad. Si un equipo necesita potencia predictiva bruta, debería usar *XGBoost*. Si necesita un modelo defendible ante un regulador, usa TreeGov.

## Referencias regulatorias

- Basilea (BCBS CRE 20.39): PD Floors.
- EBA/GL/2017/16: validación de parámetros PD/LGD.
- IFRS 9: clasificación por etapas y ECL.
- SR 11-7 / OCC 2011-12: Model Risk Management.

## Metodología de trabajo

TreeGov se desarrolla con asistencia de IA bajo un flujo con disciplina MRM:

- Rigor metodológico: Diseñar, luego auditar el diseño, luego implementar, luego testear, luego documentar. Nunca se codifica sin auditar el diseño primero.
- Ráfagas cortas, verificación al final del bloque. Los prompts de una sub-fase se agrupan; la suite de tests se ejecuta al cerrar cada bloque, no entre prompts. Esto preserva la caché del proveedor de IA, reduce el coste, y mantiene la verificación como un punto de control claro.
- Verificación empírica mayor que obediencia ciega. El asistente de IA puede reportar éxito sin haber ejecutado la tarea. Por eso cada commit exige `pytest` verde, `git status` limpio y `git diff --stat` coherente antes de aceptar el cambio.
- Ningún agente corre solo durante horas o días. Cada cambio afecta invariantes estructurales (por ejemplo, la paridad binaria K=2 desde la Fase 3.1, o los invariantes de `TreeModel`). El humano audita cada sub-fase. Los agentes de larga duración tienen su lugar en proyectos desechables o de bajo riesgo; no en un modelo auditable por un regulador.
- Documentación de cierre obligatoria. Cada sub-fase cierra con la actualización sincronizada de los documentos de estado, contexto y bitácora. Nada se aplaza a la siguiente sesión.

## Desarrollo vs uso final: dos regímenes de datos distintos

TreeGov se desarrolla hoy con datasets públicos (German Credit, UCI) y sintéticos. Durante el desarrollo, la regla de privacidad es estricta: nunca se envían datos reales a APIs de IA de terceros. Solo se comparte código *open source*, documentación pública y datos sintéticos.

Cuando TreeGov se use en producción, el escenario es otro: el analista carga su propio *CSV* con datos reales en su escritorio, y el modelo se entrena y evalúa localmente. Los datos nunca salen del equipo del analista. TreeGov no tiene servidor, ni autenticación remota, ni base de datos, ni conexión a internet en tiempo de ejecución.

Esta distinción tiene consecuencias que el proyecto asume explícitamente:

- *Los logs DEBUG* contienen información sensible. Cuando se entrena sobre datos reales, el log registra PD por nodo, distribuciones de hojas, nombres de columnas del *CSV* real, fingerprint del modelo y rutas de archivo. El analista debe tratarlos como material confidencial.
- Los reports *HTML* exportados contienen información sensible. Gains table, matriz de clasificación, conteos por segmento, PD por hoja. Compartir un reporte es compartir parte del modelo.
- La política de datos sensibles se trata como trabajo explícito. Antes de declarar la versión 1.0.0 estable, el proyecto planifica un bloque específico de auditoría de seguridad y privacidad: retención y limpieza de logs, advertencias en la *GUI*, y un documento dedicado al modelo de amenazas.

Resumen operativo: durante el desarrollo, cero datos reales en APIs de IA. En uso final, los datos quedan en el escritorio del analista, bajo su responsabilidad y las políticas de su institución.

Nota sobre estabilidad poblacional: aunque el entrenamiento aplica filtros estrictos (ej. excluir categorías Indet/No Perf), el monitoreo de estabilidad (PSI/CSI) puede y debe evaluarse sobre la población total de admisión para capturar la deriva real.

## Cómo se refleja esto en el diseño

La filosofía no es abstracta: se traduce en decisiones de diseño
concretas y auditables en el código.

- Arquitectura de sala limpia → `backend_v3/` no tiene imports de
  GUI; `frontend_v3/` no tiene lógica analítica. Se verifica con un
  test basado en AST (`test_frontend_clean_room`).
- Matemática de caja blanca → Cada fórmula estadística está escrita
  explícitamente, con citas bibliográficas (Kass 1980, Breiman 1984,
  Loh & Shih 1997, Cochran 1954). Las librerías de caja negra
  (sklearn, statsmodels) se bloquean a nivel de intérprete mediante
  `backend_v3/import_guard.py`.
- Gobernanza nativa → `SplitConfig` es un *dataclass frozen*
  (evidencia auditable inmutable); `params_fingerprint` identifica cada
  modelo de forma única; el logger transaccional DEBUG registra cada
  decisión.
- Gobernanza opcional, modo regulatorio por defecto → `GovernanceMode`
  (REGULATORY / RESEARCH) hace que la capa regulatoria sea opt-out,
  abriendo la herramienta a dominios no bancarios (salud, ciencias
  sociales) sin sacrificar el rigor MRM donde importa. Aunque nació en
  riesgo de crédito, TreeGov puede utilizarse en cualquier dominio donde
  la trazabilidad, la explicabilidad y la gobernanza sean importantes.

---
*[Read in English](philosophy.md)*
