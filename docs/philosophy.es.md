# Filosofía TreeGov

## La frase central

> "Python le da el motor. TreeGov le da el motor, el freno, el tablero, el cinturón de seguridad y el registro de mantenimiento. ¿Cuál prefiere para un modelo que va a ser auditado por el regulador?"

## Por qué existe TreeGov

Existe una generación de analistas de riesgo que necesita herramientas GUI para construir árboles auditables, y las herramientas que existían fueron descontinuadas sin reemplazo. Las librerías estadísticas y los entornos de scripting ofrecen potencia analítica, pero no gobernanza nativa. TreeGov llena ese vacío.

## El diferenciador

La gobernanza no es un añadido. Es el punto de partida:

- Configuración inmutable (SplitConfig frozen) = evidencia auditable.
- Logging DEBUG transaccional = trazabilidad regulatoria.
- Caja blanca matemática = fórmulas citables y verificables.
- Bloqueo de librerías de caja negra = auditabilidad por diseño.

## A quién sirve

- Analistas de riesgo de crédito que quieren dedicar tiempo al análisis, no a la programación.
- Equipos de validación MRM que necesitan trazabilidad completa.
- Reguladores que exigen auditabilidad de modelos de PD y clasificación.

## Compromiso

TreeGov no compite en precisión predictiva bruta. Compite en gobernanza y auditabilidad. Si un banco necesita XGBoost para ganar 2 puntos de AUC, que use Python. Si necesita un modelo defendible ante un regulador, usa TreeGov.

## Referencias regulatorias

- Basilea (BCBS CRE 20.39): PD Floors.
- EBA/GL/2017/16: validación de parámetros PD/LGD.
- IFRS 9: clasificación por etapas y ECL.
- SR 11-7 / OCC 2011-12: Model Risk Management.

## Cómo se refleja esto en el diseño

La filosofía no es abstracta: se traduce en decisiones de diseño
concretas y auditables en el código.

- **Arquitectura de sala limpia** → `backend_v3/` no tiene imports de
  GUI; `frontend_v3/` no tiene lógica analítica. Se verifica con un
  test basado en AST (`test_frontend_clean_room`).
- **Matemática de caja blanca** → Cada fórmula estadística está escrita
  explícitamente, con citas bibliográficas (Kass 1980, Breiman 1984,
  Loh & Shih 1997, Cochran 1954). Las librerías de caja negra
  (sklearn, statsmodels) se bloquean a nivel de intérprete mediante
  `backend_v3/import_guard.py`.
- **Gobernanza nativa** → `SplitConfig` es un dataclass frozen
  (evidencia auditable inmutable); `params_fingerprint` identifica cada
  modelo de forma única; el logger transaccional DEBUG registra cada
  decisión.
- **Gobernanza opcional, banking por defecto** → `GovernanceMode`
  (BANKING / RESEARCH) hace que la capa regulatoria sea opt-out,
  abriendo la herramienta a dominios no bancarios (salud, ciencias
  sociales) sin sacrificar el rigor MRM donde importa.

---
*[Read in English](philosophy.md)*
