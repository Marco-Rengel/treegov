# Documentación Metodológica y Matemática (MRM / IFRS 9)
## Plataforma Analítica DecisionTree_Modeler

**Versión del Modelo**: 3.0.0 (Sprint 3 / MRM Refactor)  
**Marco Normativo de Referencia**:
* **BCBS (Basel Committee on Banking Supervision)**: CRE 20.39 (*Regulatory Probability of Default Floors*).
* **EBA/GL/2017/16**: Directrices sobre especificación, estimación y validación de parámetros PD/LGD en modelos internos (IRB).
* **NIIF 9 / IFRS 9**: Clasificación por etapas (*Staging*), Pérdida Crediticia Esperada (*ECL*) y optimización de umbrales decisionales asimétricos.
* **SR 11-7 / OCC 2011-12**: Guía sobre Gestión del Riesgo de Modelos (*Model Risk Management - MRM*).

---

## 1. Algoritmos de Inducción de Árboles de Decisión

El motor analítico implementado en [`backend/split_engine.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/split_engine.py) y [`backend/tree_builder.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/tree_builder.py) soporta tres algoritmos de crecimiento:

### 1.1. Algoritmo CHAID (*Chi-square Automatic Interaction Detection*)
CHAID particiona recursivamente la población en función de la significancia estadística de la asociación entre cada variable predictora $X$ y la variable objetivo binaria $Y \in \{0, 1\}$.

1. **Fusión de Categorías (*Category Merging*)**:
   Para cada par de categorías contiguas (en variables numéricas o continuas discretizadas) o cualquier par (en variables nominales), se construye una tabla de contingencia de dimensión $2 \times 2$. Se evalúa el estadístico de Pearson:
   $$\chi^2 = \sum_{i=1}^2 \sum_{j=1}^2 \frac{(O_{ij} - E_{ij})^2}{E_{ij}}$$
   donde $O_{ij}$ son las frecuencias observadas y $E_{ij} = \frac{R_i \cdot C_j}{N}$ las frecuencias esperadas bajo independencia.
   Se calcula el valor $p$ asociado a 1 grado de libertad. Si el valor $p$ más alto supera el umbral $\alpha_{\text{merge}}$ (`alpha_merge`), las dos categorías se fusionan. El proceso se repite iterativamente hasta que todos los pares restantes satisfagan $p \le \alpha_{\text{merge}}$.

2. **Ajuste de Bonferroni**:
   Para evitar la inflación del error Tipo I debido al número de posibles particiones simultáneas, el valor $p$ final de la variable $X$ se ajusta multiplicándolo por el multiplicador combinatorio de Bonferroni $B(c, r)$:
   $$p_{\text{adj}} = p \cdot B(c, r)$$
   donde $c$ es el número original de categorías y $r$ es el número de categorías resultantes tras la fase de fusión.

3. **Selección y División (*Splitting*)**:
   Entre todas las variables predictoras candidatas con $p_{\text{adj}} \le \alpha_{\text{split}}$ (`alpha_split`), se selecciona la covariable con el menor $p_{\text{adj}}$ (máxima significancia estadística). Si ninguna variable satisface la condición o si el número de registros es inferior a `min_parent_node`, el nodo se convierte en hoja terminal.

### 1.2. Exhaustive CHAID
Variación exhaustiva que no se detiene en el primer agrupamiento local óptimo. Continúa fusionando categorías hasta reducirlas a solo dos categorías compuestas, evaluando en cada paso el estadístico de prueba. Posteriormente, selecciona la partición que maximizó el estadístico de Chi-cuadrado ajustado por Bonferroni, incrementando la robustez en muestras con distribuciones complejas o ruido moderado.

### 1.3. Algoritmo CRT (*Classification and Regression Trees*)
Implementa la partición binaria recursiva guiada por la impureza de Gini. Para un nodo $t$ con proporción de malos $p(1|t) = \frac{n_1(t)}{N(t)}$ y proporción de buenos $p(0|t) = 1 - p(1|t)$:

$$\text{Gini}(t) = 1 - \left( [p(0|t)]^2 + [p(1|t)]^2 \right) = 2 \cdot p(1|t) \cdot (1 - p(1|t))$$

Para un punto de corte candidato $s$ que divide el nodo $t$ en dos subnodos hijos $t_L$ (izquierdo) y $t_R$ (derecho):
$$\Delta \text{Gini}(s, t) = \text{Gini}(t) - \left[ \frac{N(t_L)}{N(t)} \text{Gini}(t_L) + \frac{N(t_R)}{N(t)} \text{Gini}(t_R) \right]$$

El algoritmo evalúa todos los cortes posibles sobre todas las variables y selecciona la partición $s^*$ que maximiza la ganancia de impureza:
$$s^* = \arg\max_s \Delta \text{Gini}(s, t)$$

---

## 2. Partición Muestral Estratificada y Asignación Exacta (Hamilton-Hare)

La representatividad muestral entre entrenamiento (*Train*) y validación fuera de muestra (*Out-of-Sample - OOS*) se garantiza mediante el método de cuotas de mayor residuo (*Largest Remainder / Hamilton-Hare*), codificado en [`backend/sample_splitter.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/sample_splitter.py).

### 2.1. Formulación del Reparto de Hamilton-Hare
Dado un conjunto de datos con $N$ observaciones totales, $N_1$ eventos ($Y=1$) y $N_0$ no-eventos ($Y=0$), y fijada una cuota objetivo de entrenamiento $N_{\text{train}}$ (definida por tamaño absoluto o por proporción $N_{\text{train}} = \text{round}(N \cdot \text{train\_pct})$):

1. Se computan las cuotas continuas ideales para cada estrato $j \in \{0, 1\}$:
   $$Q_j = N_j \cdot \left( \frac{N_{\text{train}}}{N} \right)$$
2. Se asigna inicialmente la parte entera inferior:
   $$n_j = \lfloor Q_j \rfloor$$
3. Se calcula el residuo de asignación:
   $$R = N_{\text{train}} - (n_0 + n_1)$$
4. Las fracciones residuales $f_j = Q_j - n_j$ determinan la asignación de las $R$ observaciones restantes: el estrato con mayor $f_j$ recibe $+1$ unidad adicional hasta agotar $R$.

Este algoritmo previene sesgos de redondeo y garantiza que la tasa observada de eventos en entrenamiento y prueba coincida exactamente con la población de desarrollo:
$$\frac{n_1}{n_0 + n_1} \approx \frac{N_1}{N}$$

### 2.2. Aislamiento Estricto de Muestra Temporal (*Out-of-Time - OOT*)
Conforme a los lineamientos de gobernanza MRM, la muestra OOT **no se genera como partición aleatoria del dataset de desarrollo**. El sistema exige la ingesta de un archivo externo e independiente (CSV, Parquet o Excel) con un horizonte temporal posterior, validando la inmunidad del modelo ante cambios de ciclo macroeconómico.

---

## 3. Estimación de Probabilidad de Incumplimiento (ALG-07 / BCBS CRE 20.39)

En árboles de decisión estándar, la probabilidad de incumplimiento de una hoja $t$ se calcula mediante la frecuencia empírica:
$$PD_{\text{empírica}}(t) = \frac{k(t)}{N(t)}$$
donde $k(t)$ es el conteo de clientes en mora y $N(t)$ la población del nodo.

### 3.1. Estimador Bayesiano de Jeffreys
En carteras de bajo impago (*Low Default Portfolios - LDP*) o en nodos terminales pequeños, $k(t) = 0$ genera una probabilidad empírica de 0%, lo que implica ausencia teórica de riesgo, violando la prudencia bancaria. El estimador bayesiano de Jeffreys incorpora una distribución a priori no informativa $\text{Beta}(\alpha=0.5, \beta=0.5)$, obteniendo la media posterior:

$$PD_{\text{Jeffreys}}(t) = \frac{k(t) + 0.5}{N(t) + 1.0}$$

* **Propiedad asintótica**: Cuando $N(t) \to \infty$, $PD_{\text{Jeffreys}}(t) \to PD_{\text{empírica}}(t)$.
* **Propiedad en nodos puros**: Si $k(t) = 0$, $PD_{\text{Jeffreys}}(t) = \frac{0.5}{N(t) + 1.0} > 0$.

### 3.2. Suelo Regulatorio de PD (*Regulatory PD Floor*)
Conforme a la normativa prudencial de **Basilea (BCBS CRE 20.39)** y los requerimientos de IFRS 9, ninguna exposición crediticia puede exhibir una probabilidad de incumplimiento inferior al umbral mínimo regulatorio (típicamente 3 puntos básicos, $0.03\% = 0.0003$).

El estimador final calibrado en cada nodo hoja $t$ (`Node.bad_rate`) está dado por:
$$PD_{\text{final}}(t) = \max\left( \text{pd\_floor}, \; PD_{\text{Jeffreys}}(t) \right)$$

---

## 4. Poder Discriminante y Estadísticos de Separación (MRM-01)

### 4.1. Coeficiente de Gini Canónico y AUC
El área bajo la curva de características operativas del receptor ($AUC$) se calcula formalmente a través del estadístico no paramétrico $U$ de Wilcoxon-Mann-Whitney sobre las probabilidades continuas de cada observación $s_i = PD_{\text{final}}(\text{hoja}_i)$:

$$U = R_1 - \frac{n_1(n_1 + 1)}{2}$$
donde $R_1$ es la suma de rangos de las observaciones con evento ($Y=1$), utilizando **rangos promedio (*mid-ranks*)** para manejar empates nodales masivos.
$$AUC = \frac{U}{n_1 \cdot n_0}$$

El Coeficiente de Gini canónico se deriva estrictamente a partir de la geometría del área acumulada:
$$\text{Gini} = 2 \cdot AUC - 1$$
El sistema garantiza que $\text{Gini} \in [0, 1]$ y rechaza el uso de *Accuracy* como sustituto de discriminación crediticia.

### 4.2. Estadístico de Kolmogorov-Smirnov (KS)
Cuantifica la máxima distancia vertical entre la función de distribución acumulada de clientes incumplidores ($F_{\text{bad}}$) y clientes cumplidores ($F_{\text{good}}$):

$$KS = \max_{s} \left| F_{\text{bad}}(s) - F_{\text{good}}(s) \right|$$

### 4.3. Degradación del Modelo (*Gini Drop*)
Para evaluar sobreajuste (*overfitting*) en muestras OOS y OOT:
$$\text{Gini Drop}_{\text{OOS}} = \frac{\text{Gini}_{\text{Train}} - \text{Gini}_{\text{OOS}}}{\text{Gini}_{\text{Train}}}$$
$$\text{Gini Drop}_{\text{OOT}} = \frac{\text{Gini}_{\text{Train}} - \text{Gini}_{\text{OOT}}}{\text{Gini}_{\text{Train}}}$$
Un $\text{Gini Drop} > 20\%$ activa una alerta preventiva de riesgo de modelo; un drop $> 40\%$ exige la recalibración o desestimación del árbol.

---

## 5. Pruebas de Calibración de Probabilidades (MRM-03)

### 5.1. Prueba de Bondad de Ajuste de Hosmer-Lemeshow
Evalúa si las probabilidades estimadas por el modelo reflejan las tasas de incumplimiento observadas a lo largo de $G$ deciles o grupos de riesgo ordenados:

$$H = \sum_{g=1}^G \frac{(O_g - N_g \bar{\pi}_g)^2}{N_g \bar{\pi}_g (1 - \bar{\pi}_g)}$$
donde:
* $N_g$: Total de créditos en el decil $g$.
* $O_g$: Defaults observados en el decil $g$.
* $\bar{\pi}_g = \frac{1}{N_g} \sum_{i \in g} \hat{p}_i$: Probabilidad promedio estimada en el decil.

Bajo la hipótesis nula $H_0$ de calibración adecuada:
$$H \sim \chi^2(G - 2)$$
Si $p > 0.05$, no se rechaza $H_0$ y el modelo se certifica como **adecuadamente calibrado**.

### 5.2. Brier Score y Brier Skill Score (BSS)
Mide la precisión probabilística media cuadrática:
$$BS = \frac{1}{N} \sum_{i=1}^N (y_i - \hat{p}_i)^2$$

Se compara contra el Brier Score del modelo nulo ($BS_{\text{ref}} = \bar{y}(1 - \bar{y})$) mediante el Brier Skill Score:
$$BSS = 1 - \frac{BS}{BS_{\text{ref}}}$$
Un $BSS > 0$ certifica que las estimaciones probabilísticas del árbol superan significativamente al pronóstico ingenuo de la tasa media de la cartera.

---

## 6. Monitoreo de Estabilidad Poblacional y de Atributos (MRM-02)

### 6.1. Índice de Estabilidad Poblacional (PSI)
Mide el desplazamiento de las masas de probabilidad asignadas a las hojas terminales del árbol entre la muestra base de referencia (Train) y la muestra actual de monitoreo (OOS/OOT/Producción):

$$PSI = \sum_{k=1}^K \left( P_{\text{actual}, k} - P_{\text{esperada}, k} \right) \cdot \ln\left( \frac{P_{\text{actual}, k}}{P_{\text{esperada}, k}} \right)$$
donde $K$ es el número de hojas terminales del árbol.

### 6.2. Índice de Estabilidad de Características (CSI)
Evalúa el corrimiento distributivo individual de cada covariable predictora $X$. Para variables numéricas, se calcula sobre deciles de la muestra de referencia; para variables categóricas, sobre sus categorías observadas.

### 6.3. Semáforo Regulatorio de Basilea / EBA
Ambos índices se clasifican bajo los umbrales estándar de la industria bancaria:
* **PSI / CSI $< 0.10$**: `STABLE` (Verde) — Distribución estable; sin acción requerida.
* **$0.10 \le$ PSI / CSI $< 0.25$**: `MODERATE` (Ámbar) — Alerta moderada; requiere seguimiento de cartera y análisis de causa raíz.
* **PSI / CSI $\ge 0.25$**: `UNSTABLE` (Rojo) — Desplazamiento severo; suspensión del modelo y recalibración obligatoria.

---

## 7. Optimización de Corte Asimétrico (IFRS 9 / MRM-04)

En el otorgamiento de crédito, los costos de clasificación errónea son severamente asimétricos:
* **Falso Negativo (FN)**: Aprobar a un cliente que incurrirá en incumplimiento. Su costo unitario es la pérdida en caso de impago sobre la exposición:
  $$C_{FN} = LGD \times EAD$$
* **Falso Positivo (FP)**: Rechazar a un cliente que hubiera pagado puntualmente. Su costo unitario es el margen de intermediación financiero neto perdido:
  $$C_{FP} = NIM$$

### 7.1. Función de Pérdida Asimétrica Crediticia
Para cualquier umbral de corte decisional $\theta \in (0, 1)$:
$$E[\text{Pérdida}](\theta) = C_{FN} \cdot FN(\theta) + C_{FP} \cdot FP(\theta)$$

### 7.2. Algoritmo de Búsqueda de Umbral Óptimo $\theta^*$
El motor evalúa una grilla densa de 99 puntos candidatos $\theta \in [0.01, 0.99]$ con paso $0.01$ y determina el punto de corte óptimo:
$$\theta^* = \arg\min_{\theta \in (0, 1)} E[\text{Pérdida}](\theta)$$

Se calcula el ahorro monetario frente al punto de corte simétrico ingenuo ($\theta = 0.50$):
$$\text{Ahorro} = E[\text{Pérdida}](0.50) - E[\text{Pérdida}](\theta^*)$$

---

## 8. Métricas Robustas ante Desbalanceo Severo (MRM-05)

Dada la baja incidencia típica de eventos en carteras de crédito ($1\% - 7\%$), el sistema provee tres métricas inmunes al desbalanceo:

1. **Media Geométrica (*G-Mean*)**:
   $$G\text{-Mean} = \sqrt{\text{Sensibilidad} \times \text{Especificidad}} = \sqrt{\left(\frac{TP}{TP+FN}\right) \cdot \left(\frac{TN}{TN+FP}\right)}$$
2. **Coeficiente de Correlación de Matthews (*MCC*)**:
   $$MCC = \frac{TP \cdot TN - FP \cdot FN}{\sqrt{(TP + FP)(TP + FN)(TN + FP)(TN + FN)}} \in [-1, 1]$$
3. **Área bajo la Curva Precisión-Cobertura (*PR-AUC*)**:
   Evalúa la compensación entre el valor predictivo positivo (*Precision*) y la cobertura (*Recall*) en todos los umbrales de decisión.

---

## 9. Motor de Exportación Dual de Reglas (SQL Jerárquico + Python Puro)

El módulo [`backend/rule_exporter.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/rule_exporter.py) garantiza la reproducibilidad analítica fuera del aplicativo:

### 9.1. SQL Jerárquico Recursivo
Construye expresiones SQL `CASE WHEN ... ELSE (CASE WHEN ...) END` anidadas que reflejan la estructura de árbol de decisión en profundidad. Cada rama bifurca el flujo lógico hasta alcanzar la hoja terminal correspondiente, asignando su `bad_rate` calibrado y su `node_id`.

### 9.2. Scorer Autónomo en Python Puro
Genera un archivo `.py` independiente con la función `score_record(record: dict) -> dict`:
* **Zero Dependencies**: No requiere `pandas`, `numpy`, `scikit-learn` ni extensiones C.
* **Tiempo de Ejecución**: Inferencia de regla condicional en tiempo constante $O(\text{depth})$ con ejecución típica inferior a 5 microsegundos por registro.
* **Retorno Completo**: Emite `node_id`, `bad_rate`, `sample_n` y `gini_impurity`.

---

## 10. Motor de Partición Asistida y Selección de Cortes Candidatos (MRM-06)

El motor de partición asistida implementado en [`backend/split_engine.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/split_engine.py) (`find_candidate_splits`) permite al modelador explorar y aplicar particiones alternativas supervisadas sobre cualquier nodo activo:

### 10.1. Criterio de Diversidad Predictora (Top-2 por Variable)
Para evitar la saturación de la grilla de candidatos con infinitas variaciones micrométricas de una única variable continua dominante (ej. múltiples puntos de corte continuos para `"ingreso_mensual"`), el algoritmo extrae un **máximo de 2 mejores candidatos por cada variable predictora evaluada**. Posteriormente, la lista consolidada de candidatos multivariados se ordena descendentemente según la métrica discriminante local seleccionada (`LOCAL_KS` o `GINI_GAIN`).

### 10.2. Métricas Locales de Discriminación
Para un nodo padre $t$ con población $N$, $k$ eventos ($Y=1$) e impureza $\text{Gini}(t)$, cada corte candidato $s$ que divide el nodo en dos ramas $t_L$ (izquierdo) y $t_R$ (derecho) es evaluado mediante las siguientes métricas estadísticas:

1. **Ganancia de Impureza de Gini Local ($\Delta \text{Gini}$)**:
   $$\Delta \text{Gini}(s, t) = \text{Gini}(t) - \left[ \frac{N_L}{N} \text{Gini}(t_L) + \frac{N_R}{N} \text{Gini}(t_R) \right]$$

2. **Estadístico Kolmogorov-Smirnov Local ($KS_{\text{local}}$)**:
   Mide la separación de distribuciones de eventos y no-eventos inducida exclusivamente entre los dos nodos hijos:
   $$KS_{\text{local}} = \left| \frac{k_L}{k} - \frac{N_L - k_L}{N - k} \right|$$

3. **Weight of Evidence ($WoE$)**:
   Calculado para cada rama hija $b \in \{L, R\}$ con regularización bayesiana $\epsilon = 0.5$:
   $$WoE_b = \ln\left( \frac{(N_b - k_b + \epsilon) / (N - k + 2\epsilon)}{(k_b + \epsilon) / (k + 2\epsilon)} \right)$$

4. **Information Value ($IV$)**:
   Cuantifica el poder predictivo total de la partición binaria:
   $$IV = \sum_{b \in \{L, R\}} \left( \frac{N_b - k_b}{N - k} - \frac{k_b}{k} \right) \cdot WoE_b$$
   * $IV < 0.02$: No predictivo.
   * $0.02 \le IV < 0.10$: Débil.
   * $0.10 \le IV < 0.30$: Medio.
   * $0.30 \le IV < 0.50$: Fuerte.
   * $IV \ge 0.50$: Sospechoso / Sobreajuste.

5. **Odds Ratio ($OR$)**:
   Razón de momios entre las dos ramas hijas:
   $$OR = \frac{\text{Odds}_L}{\text{Odds}_R} = \frac{(k_L + \epsilon) / (N_L - k_L + \epsilon)}{(k_R + \epsilon) / (N_R - k_R + \epsilon)}$$

6. **Significancia Estadística Pearson ($\chi^2$ y $p$-valor)**:
   Contraste de independencia sobre la tabla de contingencia $2 \times 2$ con 1 grado de libertad.

### 10.3. Gobernanza de Nodos Congelados (*Frozen Nodes*) y Bitácora de Intervenciones
Conforme al marco MRM, cualquier nodo intervenido o validado puede ser marcado como congelado (`is_frozen = True`). 
* Un nodo congelado queda blindado contra auto-crecimiento o sobreescritura accidental.
* Cualquier aplicación de corte forzado sobre un nodo congelado exige justificación formal obligatoria registrada en la bitácora de auditoría inmutable [`backend/audit_trail.py`](file:///c:/Riesgos/DecisionTree_Modeler/backend/audit_trail.py) (`AuditTrail`), preservando la trazabilidad exigida por la norma SR 11-7.

