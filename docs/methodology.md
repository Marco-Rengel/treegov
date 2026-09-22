# Metodología Matemática — TreeGov

Documentación formal de los algoritmos implementados en TreeGov con sus fundamentos matemáticos y citas bibliográficas.

---

## 1. CHAID clásico y Exhaustive CHAID

CHAID (Chi-square Automatic Interaction Detection) particiona recursivamente la población evaluando la asociación estadística entre cada predictor y la variable objetivo.

### 1.1. Chi-cuadrado de Pearson

Para una tabla de contingencia observada de I×J celdas:

χ² = Σᵢⱼ (O_ij − E_ij)² / E_ij

donde:
- O_ij: frecuencia observada en la celda (i, j).
- E_ij = R_i · C_j / N: frecuencia esperada bajo independencia.
- R_i: marginal de la fila i.
- C_j: marginal de la columna j.
- N: total de observaciones.

Grados de libertad: gl = (I − 1)(J − 1).

Sin corrección de continuidad de Yates (convención CHAID original).

**Cita**: Pearson, K. (1900). Philosophical Magazine, Ser. 5, 50(302), 157-175.

### 1.2. ANOVA unifactorial (F de Fisher)

Para k grupos con n_i observaciones cada uno:

SS_B = Σᵢ nᵢ (ȳᵢ − ȳ)²     (entre grupos)
SS_W = Σᵢ Σⱼ (y_ij − ȳᵢ)²   (dentro de grupos)
df1 = k − 1 ; df2 = N − k
F = (SS_B / df1) / (SS_W / df2)

p-valor = P(F_{df1,df2} ≥ F) vía función de supervivencia.

**Cita**: Fisher, R.A. (1925). Statistical Methods for Research Workers.

### 1.3. Fusión iterativa de categorías

Para cada par de categorías elegibles:

1. Construir subtabla 2×K del par.
2. Calcular χ² (target categórico) o F (target continuo).
3. Fusionar el par con mayor p-valor si p > α_merge.
4. Repetir hasta que ningún par sea fusionable.

En predictores ordinales, solo se consideran pares adyacentes.

### 1.4. Multiplicadores de Bonferroni de Kass (1980)

Para una variable con c categorías originales que termina en r grupos tras la fusión:

- **Predictor ordinal**: M(c, r) = C(c − 1, r − 1) = (c−1)! / [(r−1)! (c−r)!]
- **Predictor nominal**: M(c, r) = S(c, r), número de Stirling de segunda especie

p_valor_ajustado = min(1, p_valor × M)

**Cita**: Kass, G.V. (1980). Applied Statistics, 29(2), 119-127.

### 1.5. Exhaustive CHAID

Variante que no se detiene en el primer óptimo local. Fusiona pares iterativamente hasta reducir a 2 grupos, registrando el historial completo de pasos. Selecciona el paso con menor p-valor ajustado (incluido el paso 0 sin fusiones).

**Cita**: Biggs, D., de Ville, B. & Suen, E. (1991). Journal of Applied Statistics, 18(1), 49-62.

### 1.6. Regla de Cochran (1954)

La aproximación asintótica de χ² pierde validez cuando:
- Alguna frecuencia esperada E_ij < 1, o
- Más del 20% de las celdas tienen E_ij < 5.

TreeGov aplica fusión forzosa preventiva de la categoría de menor total hasta satisfacer la regla. Si es irreductible (r = 2), se reporta cochran_ok = False con WARNING.

**Cita**: Cochran, W.G. (1954). Biometrics, 10(4), 417-451.

---

## 2. C&RT (Classification and Regression Trees)

Árbol estrictamente binario guiado por reducción de impureza.

### 2.1. Impureza de Gini

Para un nodo t con K clases y proporciones p_k = n_k / n:

I_Gini(t) = 1 − Σₖ p_k²

### 2.2. Impureza por varianza

Para regresión:

I_Var(t) = (1/n) Σᵢ (yᵢ − μ)² = E[y²] − E[y]²

### 2.3. Reducción de impureza

Para un corte s que divide el nodo t en hijos L (izquierda) y R (derecha):

ΔI(s, t) = I(t) − (n_L / N) · I(L) − (n_R / N) · I(R)

El corte óptimo es el que maximiza ΔI.

### 2.4. Búsqueda de umbrales (continuo)

Para una variable continua, se ordenan los valores y se evalúan los puntos medios entre valores distintos consecutivos:

t_i = (x_(i) + x_(i+1)) / 2

El umbral elegido es el que maximiza ΔI.

### 2.5. Subconjuntos (nominal)

Para variables nominales con K ≤ 10 categorías: búsqueda exhaustiva de las 2^(K−1) − 1 particiones binarias no triviales.

Para K > 10: heurística por tasa de la clase mayoritaria (ordenamiento supervisado).

### 2.6. Surrogate splits

Replicas de asignación izquierda/derecha sobre predictores secundarios, usadas para enrutar valores nulos. Se ordenan por agreement con el split primario y se retienen los que superan el majority.

**Cita**: Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.

---

## 3. QUEST (Quick, Unbiased, Efficient Statistical Tree)

Motor binario con selección insesgada de variable y corte por QDA univariante.

### 3.1. Etapa 1 — Selección de variable

Para cada predictor j:

- Continuo/ordinal: pⱼ = p-valor del F-test ANOVA entre clases.
- Nominal: pⱼ = p-valor del χ² de Pearson.

Umbral Bonferroni: α / (2J), donde J = número de predictores.

Si ningún test supera el umbral, se ejecuta Brown-Forsythe (Levene con mediana) sobre las variables continuas/ordinales para detectar discriminación por varianza.

### 3.2. Etapa 2 — Corte QDA univariante

Se estiman, por clase k ∈ {0, 1}: n_k, m_k (media), s_k² (varianza muestral), π_k = n_k / N.

La frontera de decisión QDA es la raíz de:

ℓ₁(x) − ℓ₀(x) = 0

donde ℓ_k(x) = −½ ln(2π) − ½ ln(s_k²) − (x − m_k)² / (2 s_k²) + ln(π_k)

Esto da una ecuación cuadrática A x² + B x + C = 0 con:

A = 1/s₀² − 1/s₁²
B = 2 (m₁/s₁² − m₀/s₀²)
C = m₀²/s₀² − m₁²/s₁² + 2 ln(π₁/π₀) − ln(s₁²/s₀²)

Se acepta la raíz dentro del rango [min(m₀, m₁), max(m₀, m₁)]. Si no hay raíz válida, fallback al punto medio ponderado x̄ = (n₀ m₀ + n₁ m₁) / N.

**Cita**: Loh, W.-Y. & Shih, Y.-S. (1997). Statistica Sinica, 7(4), 815-840.

---

## 4. SplitConfig — Contrato común entre motores

Todos los motores (CHAID, C&RT, QUEST) devuelven objetos `SplitConfig`, un dataclass inmutable (frozen) que actúa como evidencia auditable de cada partición candidata.

### 4.1. Campos

- predictor: nombre del predictor evaluado.
- method: "CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST".
- statistic: valor del estadístico observado.
- statistic_name: "chi2", "f", "gini_gain" o "variance_gain".
- df: tupla de grados de libertad.
- parent_n: tamaño del nodo padre.
- child_ns: tamaños de los nodos hijos.
- p_value: p-valor crudo (None en C&RT).
- p_value_adjusted: p-valor ajustado por Bonferroni.
- bonferroni_multiplier: M de Kass aplicado.
- n_merges: número de fusiones aplicadas.
- threshold: umbral numérico (solo continuo).
- branches: grupos de categorías por rama (solo categórico).
- impurity_gain: ganancia de impureza (solo C&RT).

### 4.2. Invariantes validados

En el constructor (__post_init__) se verifica:
- method ∈ {"CHAID", "CHAID_EXHAUSTIVE", "CRT", "QUEST"}.
- Coherencia method ↔ statistic_name ↔ campos obligatorios.
- Exactamente uno de threshold / branches está definido.
- branches forma una partición real (grupos no vacíos, categorías disjuntas).
- len(child_ns) coincide con el número de ramas.
- sum(child_ns) ≤ parent_n.
- p_value_adjusted ≥ p_value (Bonferroni nunca reduce).

---

## 5. Imputación anti-leakage (TrainOnlyImputer)

### 5.1. Regla MRM

Los estadísticos de imputación (media para continuas, moda para categóricas) se calculan EXCLUSIVAMENTE sobre el fold de entrenamiento. El mismo valor se aplica a cualquier otro fold (test, OOS, OOT).

### 5.2. Justificación

Calcular la media sobre el dataset completo introduce data leakage: el modelo "ve" información del test antes de ser evaluado. La imputación train-only evita esta fuga y es requisito regulatorio (SR 11-7).

### 5.3. Determinismo en empates

Si hay empate en la moda:
- Etiquetas ordenables → la menor.
- Etiquetas no comparables → primera por orden de aparición (recorrido secuencial, no por orden interno de pandas).

---

## 6. Estimador de Jeffreys y PD Floor

### 6.1. PD empírica

PD_empírica(t) = k(t) / N(t)

donde k(t) es el conteo de eventos en el nodo t y N(t) su población.

### 6.2. Estimador bayesiano de Jeffreys

Distribución a priori no informativa Beta(0.5, 0.5). Media posterior:

PD_Jeffreys(t) = (k(t) + 0.5) / (N(t) + 1.0)

Propiedad: cuando N(t) → ∞, PD_Jeffreys → PD_empírica.
Propiedad: si k(t) = 0, PD_Jeffreys > 0 siempre.

### 6.3. Suelo regulatorio

Ninguna exposición puede tener PD inferior a 0.03% (3 bps) conforme a Basilea (BCBS CRE 20.39):

PD_final(t) = max(PD_floor, PD_Jeffreys(t))

**Cita**: Basilea (BCBS CRE 20.39), EBA/GL/2017/16, IFRS 9.

---

## 7. Partición Hamilton-Hare (Largest Remainder)

Para un dataset con N observaciones y cuota objetivo de entrenamiento N_train = round(N × train_frac):

Por estrato j (j ∈ {0, 1} para target binario):

1. Cuota ideal: Q_j = N_j × (N_train / N).
2. Parte entera: n_j = floor(Q_j).
3. Resto: R = N_train − (n_0 + n_1).
4. Asignación de las R observaciones restantes: las clases con mayor fracción residual f_j = Q_j − n_j reciben +1 unidad.

Garantiza que la tasa de eventos en train coincida exactamente con la población.

---

## 8. Métricas de validación

### 8.1. Gini canónico

> **Nota sobre convenciones de Gini.** TreeGov utiliza
> **Gini = 2·AUC − 1**, donde AUC se calcula por
> Wilcoxon-Mann-Whitney con mid-ranks. Esta es la convención estándar
> en credit scoring y MRM bancario.
>
> NO confundir con:
> - La convención alternativa **Gini = AUC − 0.5** (rango 0 a 0.5),
>   usada en algunos contextos académicos.
> - El **coeficiente de Gini económico** (desigualdad de ingresos).
>
> La confusión entre estas tres convenciones es común en la industria;
> documentar la elegida es requisito de trazabilidad MRM.

Derivado del área bajo la curva ROC (AUC) mediante el estadístico U de Wilcoxon-Mann-Whitney:

AUC = U / (n_1 × n_0)
Gini = 2 × AUC − 1

donde U = R_1 − n_1(n_1 + 1)/2, con R_1 la suma de rangos de las observaciones con evento (usando mid-ranks para empates).

### 8.2. Kolmogorov-Smirnov

KS = max_s |F_bad(s) − F_good(s)|

Máxima distancia vertical entre las funciones de distribución acumulada de eventos y no-eventos.

### 8.3. Hosmer-Lemeshow

H = Σ_g (O_g − N_g π̄_g)² / [N_g π̄_g (1 − π̄_g)]

Bajo H₀: H ~ χ²(G − 2), donde G es el número de grupos (típicamente 10 deciles).

Si p > 0.05, no se rechaza H₀ (modelo calibrado).

### 8.4. Brier Score y BSS

BS = (1/N) Σᵢ (yᵢ − p̂ᵢ)²
BSS = 1 − BS / BS_ref

donde BS_ref = ȳ(1 − ȳ) es el Brier Score del modelo nulo.

### 8.5. PSI y CSI

PSI = Σ_k (P_actual,k − P_esperada,k) × ln(P_actual,k / P_esperada,k)

Semáforos regulatorios (Basilea / EBA):
- PSI < 0.10 → STABLE (verde).
- 0.10 ≤ PSI < 0.25 → MODERATE (ámbar).
- PSI ≥ 0.25 → UNSTABLE (rojo).

CSI aplica la misma fórmula pero por covariable individual.

### 8.6. Optimización de corte asimétrico (IFRS 9)

Función de pérdida esperada:

E[Pérdida](θ) = C_FN × FN(θ) + C_FP × FP(θ)

donde:
- C_FN = LGD × EAD (costo de falso negativo).
- C_FP = NIM (costo de falso positivo).

Se busca θ* = argmin_θ E[Pérdida](θ) mediante búsqueda en grilla.

---

## Referencias bibliográficas completas

- Biggs, D., de Ville, B. & Suen, E. (1991). A Method of Choosing Multiway Partitions for Classification and Decision Trees. Journal of Applied Statistics, 18(1), 49-62.
- Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984). Classification and Regression Trees. Wadsworth.
- Cochran, W.G. (1954). Some Methods for Strengthening the Common Chi-2 Tests. Biometrics, 10(4), 417-451.
- Fisher, R.A. (1925). Statistical Methods for Research Workers. Oliver & Boyd.
- Kass, G.V. (1980). An Exploratory Technique for Investigating Large Quantities of Categorical Data. Applied Statistics, 29(2), 119-127.
- Loh, W.-Y. & Shih, Y.-S. (1997). Split Selection Methods for Classification Trees. Statistica Sinica, 7(4), 815-840.
- Pearson, K. (1900). On the criterion that a given system of deviations from the probable in the case of a correlated system of variables is such that it can be reasonably supposed to have arisen from random sampling. Philosophical Magazine, Ser. 5, 50(302), 157-175.

---

## Estándares regulatorios de referencia

- **Basilea (BCBS CRE 20.39)**: PD Floors regulatorios.
- **EBA/GL/2017/16**: directrices sobre especificación, estimación y validación de parámetros PD/LGD en modelos IRB.
- **IFRS 9 / NIIF 9**: clasificación por etapas (Staging), ECL y optimización de umbrales.
- **SR 11-7 / OCC 2011-12**: guía de gestión del riesgo de modelos (MRM).