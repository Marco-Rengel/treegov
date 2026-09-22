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

---
*[Read in English](philosophy.md)*
