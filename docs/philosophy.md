# TreeGov Philosophy

## The core sentence

> "Python gives you the engine. TreeGov gives you the engine, the brakes, the dashboard, the seatbelt, and the maintenance log. Which would you choose for a model that will be audited by the regulator?"

## Why TreeGov exists

There is a generation of risk analysts who need GUI tools to build auditable trees, and the tools that existed were discontinued without replacement. Statistical libraries and scripting environments offer analytical power, but not native governance. TreeGov fills that void.

## The differentiator

Governance is not an add-on. It is the starting point:

- Immutable configuration (frozen SplitConfig) = auditable evidence.
- Transactional DEBUG logging = regulatory traceability.
- White-box mathematics = citable and verifiable formulas.
- Black-box library blocking = auditability by design.

## Who it serves

- Credit risk analysts who want to spend time on analysis, not programming.
- MRM validation teams that need full traceability.
- Regulators who demand auditability of PD and classification models.

## Commitment

TreeGov does not compete on raw predictive accuracy. It competes on governance and auditability. If a bank needs XGBoost to gain 2 AUC points, it should use Python. If it needs a model that can be defended before a regulator, it uses TreeGov.

## Regulatory references

- Basel (BCBS CRE 20.39): PD Floors.
- EBA/GL/2017/16: PD/LGD parameter validation.
- IFRS 9: staging and ECL.
- SR 11-7 / OCC 2011-12: Model Risk Management.

## Metodología de trabajo

TreeGov se desarrolla con asistencia de IA bajo un flujo con disciplina MRM:

- **Rigor metodológico:** Diseñar, luego auditar el diseño, luego implementar, luego testear, luego documentar. Nunca se codifica sin auditar el diseño primero.
- **Ráfagas cortas, verificación al final del bloque.** Los prompts de una sub-fase se agrupan; la suite de tests se ejecuta al cerrar cada bloque, no entre prompts. Esto preserva la caché del proveedor de IA, reduce el coste, y mantiene la verificación como un punto de control claro.
- **Verificación empírica mayor que obediencia ciega.** El asistente de IA puede reportar éxito sin haber ejecutado la tarea. Por eso cada commit exige `pytest` verde, `git status` limpio y `git diff --stat` coherente antes de aceptar el cambio.
- **Ningún agente corre solo durante horas o días.** Cada cambio afecta invariantes estructurales (por ejemplo, la paridad binaria K=2 desde la Fase 3.1, o los invariantes de `TreeModel`). El humano audita cada sub-fase. Los agentes de larga duración tienen su lugar en proyectos desechables o de bajo riesgo; no en un modelo auditable por un regulador.
- **Documentación de cierre obligatoria.** Cada sub-fase cierra con la actualización sincronizada de los documentos de estado, contexto y bitácora. Nada se aplaza a la siguiente sesión.

## Desarrollo vs uso final: dos regímenes de datos distintos

TreeGov se desarrolla hoy con datasets públicos (German Credit, UCI) y sintéticos. Durante el desarrollo, la regla de privacidad es estricta: nunca se envían datos reales a APIs de IA de terceros. Solo se comparte código open source, documentación pública y datos sintéticos.

Cuando TreeGov se use en producción, el escenario es otro: el analista carga su propio CSV con datos reales en su escritorio, y el modelo se entrena y evalúa localmente. Los datos nunca salen del equipo del analista. TreeGov no tiene servidor, ni autenticación remota, ni base de datos, ni conexión a internet en tiempo de ejecución.

Esta distinción tiene consecuencias que el proyecto asume explícitamente:

- **Los logs DEBUG contienen información sensible.** Cuando se entrena sobre datos reales, el log registra PD por nodo, distribuciones de hojas, nombres de columnas del CSV real, fingerprint del modelo y rutas de archivo. El analista debe tratarlos como material confidencial.
- **Los reports HTML exportados contienen información sensible.** Gains table, matriz de clasificación, conteos por segmento, PD por hoja. Compartir un reporte es compartir parte del modelo.
- **La política de datos sensibles se trata como trabajo explícito.** Antes de declarar la versión 1.0.0 estable, el proyecto planifica un bloque específico de auditoría de seguridad y privacidad: retención y limpieza de logs, advertencias en la GUI, y un documento dedicado al modelo de amenazas.

Resumen operativo: durante el desarrollo, cero datos reales en APIs de IA. En uso final, los datos quedan en el escritorio del analista, bajo su responsabilidad y las políticas de su institución.

## How this maps to the design

The philosophy is not abstract: it translates into concrete design
decisions that are auditable in the source code.

- **Clean-room architecture** → `backend_v3/` has zero GUI imports;
  `frontend_v3/` has zero analytical logic. Enforced by an AST-based
  test (`test_frontend_clean_room`).
- **White-box mathematics** → Every statistical formula is written
  explicitly, with bibliographic citations (Kass 1980, Breiman 1984,
  Loh & Shih 1997, Cochran 1954). Black-box libraries (sklearn,
  statsmodels) are blocked at the interpreter level by
  `backend_v3/import_guard.py`.
- **Native governance** → `SplitConfig` is a frozen dataclass (immutable
  auditable evidence); `params_fingerprint` identifies every model
  uniquely; the DEBUG transactional logger records each decision.
- **Optional governance, banking by default** → `GovernanceMode`
  (BANKING / RESEARCH) makes the regulatory layer opt-out, opening the
  tool to non-banking domains (health, social sciences) without
  sacrificing MRM rigor where it matters.

---
*[Leer en español](philosophy.es.md)*
