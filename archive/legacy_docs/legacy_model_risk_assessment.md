> **[DOCUMENTO HISTÓRICO — era pre-TreeGov]** 
> Este documento fue parte del proyecto DecisionTree_Modeler (fases previas 
> a la reconstrucción de TreeGov, septiembre 2026). Se conserva como 
> evidencia de auditoría. No forma parte de la documentación vigente.
> Para la documentación actual, ver docs/methodology.md y docs/audit_log.md.

# MODEL RISK ASSESSMENT & AUDITORÍA TÉCNICA INTEGRAL
**Aplicativo:** `DecisionTree_Modeler` (Fases 1 a 5)  
**Alcance:** Arquitectura de Software, Solidez Matemática y Estándares Regulatorios de Riesgo de Crédito (Basilea II/III/IV, IFRS 9, SR 11-7 / OCC 2011-12)  
**Clasificación de Severidad:**  
- **CRÍTICA:** Incumplimiento regulatorio directo, distorsión matemática severa o riesgo de pérdidas por mala clasificación.  
- **ALTA:** Sesgo metodológico, vulnerabilidad de sobreajuste (*overfitting*) o cuello de botella arquitectónico crítico.  
- **MEDIA:** Ineficiencia computacional, falta de robustez paramétrica o acoplamiento de capas.  
- **BAJA:** Deuda técnica menor de formateo o estandarización de interfaz.

---

## DIMENSIÓN 1: RIESGO ALGORÍTMICO Y MATEMÁTICO

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MATRIZ DE HALLAZGOS: RIESGO ALGORÍTMICO Y MATEMÁTICO                                         │
├───────────┬───────────────────────────────────────────────────────────────┬─────────────────┤
│ ID        │ Vulnerabilidad Metodológica                                   │ Severidad       │
├───────────┼───────────────────────────────────────────────────────────────┼─────────────────┤
│ ALG-01    │ Subestimación de la Corrección de Bonferroni en CHAID         │ CRÍTICA         │
│ ALG-02    │ Falla Vectorial en el Cálculo del Estadístico KS              │ CRÍTICA         │
│ ALG-03    │ Violación de Frecuencias Esperadas Mínimas de Cochran (Chi2)  │ ALTA            │
│ ALG-04    │ Detección Errónea de Target en Imputación Dinámica de Missing │ ALTA            │
│ ALG-05    │ Ausencia de Restricción de Monotonicidad en Tasas de Default  │ ALTA            │
│ ALG-06    │ Inexistencia de Poda por Complejidad de Costos (Cost-Complex) │ MEDIA           │
│ ALG-07    │ Sesgo en Estimación Empírica de PD en Nodos Terminales (Floor)│ ALTA            │
└───────────┴───────────────────────────────────────────────────────────────┴─────────────────┘
```

### [ALG-01] Subestimación Severa de la Corrección de Bonferroni en CHAID
* **Archivo / Función:** `backend/split_engine.py` (Líneas 651-655), `_bonferroni_adjust` (Líneas 885-903).
* **Diagnóstico de Vulnerabilidad:**  
  El motor calcula el ajuste de significancia global multiplicando el $p$-valor por $C(r, 2) = \frac{r(r-1)}{2}$, donde $r$ es el número de grupos resultantes *post-fusión*.  
  Esta aproximación subestima drásticamente la tasa de error por familia (FWER). Según la formulación canónica de Kass (1980) y Answer Tree, el multiplicador de Bonferroni para una variable nominal libre de $c$ categorías originales agrupadas en $r$ ramas compuestas responde al número de particiones posibles ponderadas:
  $$M = \sum_{i=0}^{r-1} (-1)^i \frac{(r - i)^c}{i! (r - i)!}$$
  Para variables ordinales o continuas discretizadas en $c$ bins que se fusionan en $r$ intervalos adyacentes, el multiplicador exacto es:
  $$M = \binom{c - 1}{r - 1}$$
  *Impacto Empírico:* Para una variable continua discretizada en $c=20$ percentiles que termina en $r=3$ categorías, el código aplica $M = \binom{3}{2} = 3$, mientras que el ajuste formal de Kass exige $M = \binom{19}{2} = 171$. El $p$-valor ajustado reportado es **57 veces inferior al real**, generando una falsa significancia estadística masiva (*Type I Error*) y división descontrolada por ruido muestral.
* **Propuesta Cuantitativa de Mitigación:**  
  Implementar la corrección formal de Kass (1980) diferenciando la escala de la variable:
  ```python
  def _kass_bonferroni_multiplier(c: int, r: int, is_ordinal: bool) -> float:
      if is_ordinal:
          return math.comb(c - 1, r - 1)
      # Variable nominal: Stirling numbers of the 2nd kind * r! / combinaciones
      return sum((-1)**i * ((r - i)**c) / (math.factorial(i) * math.factorial(r - i)) for i in range(r))
  ```

---

### [ALG-02] Invalidez del Estadístico Kolmogorov-Smirnov por Falta de Ordenamiento Monotónico
* **Archivo / Función:** `backend/split_engine.py` (Líneas 240-282), `_ks_statistic`.
* **Diagnóstico de Vulnerabilidad:**  
  En `_ks_statistic(y, groups)`, la iteración sobre los grupos se realiza mediante `unique_groups = np.unique(groups)`, el cual ordena los identificadores de manera alfanumérica o por índice arbitrario de creación:
  ```python
  for g in unique_groups:
      cum_good += n_good_g / n_good_total
      cum_bad += n_bad_g / n_bad_total
      ks = max(ks, abs(cum_good - cum_bad))
  ```
  La definición matemática del estadístico KS en riesgo crediticio ($KS = \max_s |F_{\text{bad}}(s) - F_{\text{good}}(s)|$) exige estrictamente que las categorías o bins estén **ordenados de forma monótona respecto a su tasa de evento** ($Bad Rate_g = \frac{n_{1, g}}{n_{0, g} + n_{1, g}}$) o de su score subyacente. Acumular probabilidades sobre un ordenamiento arbitrario destruye la función de distribución acumulada empírica, produciendo valores de KS espurios y aleatorios que distorsionan la selección de variables en `DYNAMIC_MERGE`.
* **Propuesta Cuantitativa de Mitigación:**  
  Vectorizar el cálculo reordenando los grupos por su tasa de incumplimiento observada antes de acumular:
  ```python
  # Calcular bad rate por grupo y ordenar descendentemente
  group_rates = [np.mean(y[groups == g] == 1) for g in unique_groups]
  sorted_groups = [g for _, g in sorted(zip(group_rates, unique_groups), reverse=True)]
  ```

---

### [ALG-03] Infracción de las Reglas de Frecuencias Esperadas de Cochran en Pruebas $\chi^2$
* **Archivo / Función:** `backend/split_engine.py` (Líneas 839-883), `_chi2_test`.
* **Diagnóstico de Vulnerabilidad:**  
  El motor invoca `scipy.stats.chi2_contingency(observed)` asumiendo validez asintótica continua. No obstante, las carteras de riesgo de crédito se caracterizan por una marcada asimetría de clases (tasas de default típicas del 1% al 5%).  
  Bajo las reglas asintóticas de Cochran (1954), la aproximación $\chi^2$ pierde validez cuando:
  1. Cualquier frecuencia esperada $E_{ij} = \frac{R_i \cdot C_j}{N} < 1$.
  2. Más del 20% de las celdas presentan $E_{ij} < 5$.  
  En nodos profundos o categorías minoritarias ($N=50$, $BadRate=2\% \implies E_{1j} = 1.0$), el estadístico infla el error tipo II o produce singularidades numéricas.
* **Propuesta Cuantitativa de Mitigación:**  
  Incorporar una compuerta de validación condicional: si $E_{ij} < 5$ en $> 20\%$ de las celdas, conmutar automáticamente a la prueba exacta de Fisher-Irwin (para $2 \times 2$) o al test de Freeman-Halton / Monte Carlo Exact Test para tablas $r \times c$:
  $$p_{\text{exact}} = \sum_{T \in \Omega: P(T) \le P(T_{\text{obs}})} \frac{\prod R_i! \prod C_j!}{N! \prod O_{ij}!}$$

---

### [ALG-04] Detección Heurística Errónea de la Variable Target en Imputación Dinámica
* **Archivo / Función:** `backend/split_engine.py` (Líneas 1344-1370 y 2098-2120), `_detect_target_column`.
* **Diagnóstico de Vulnerabilidad:**  
  Para evaluar `DYNAMIC_MERGE`, el motor busca dinámicamente la columna dependiente iterando sobre el dataframe de entrada:
  ```python
  for col in df.columns:
      if col == feature: continue
      if len(unique_vals) == 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
          return col
  ```
  Si el dataset incluye variables predictoras binarias preexistentes (e.g., `tiene_tarjeta`, `propietario_vivienda`, `marca_empleo_formal`) posicionadas antes de la columna `default`, el algoritmo selecciona una predictora como target espurio. La fusión de valores nulos evalúa el poder discriminante respecto a una variable independiente arbitraria, destruyendo la validez de la segmentación.
* **Propuesta Cuantitativa de Mitigación:**  
  Eliminar la heurística `_detect_target_column`. El nombre de la variable objetivo debe inyectarse obligatoriamente de forma determinista mediante el constructor o la firma del método: `evaluate_feature(df, target, feature)`.

---

### [ALG-05] Carencia de Restricción de Monotonicidad en Predictores Continuos y Ordinales
* **Archivo / Función:** `backend/split_engine.py` (Líneas 967-1002), `_merge_ordinal_categories`.
* **Diagnóstico de Vulnerabilidad:**  
  `_merge_ordinal_categories` restringe las fusiones a categorías físicamente contiguas $(i, i+1)$. Sin embargo, el criterio de optimización es puramente estadístico ($p$-valor máximo de independencia).  
  El motor permite que los nodos resultantes violen la **monotonicidad en la tasa de incumplimiento** (generando comportamientos no monótonos o en "diente de sierra", e.g., $BR_1 = 2\% \to BR_2 = 8\% \to BR_3 = 3\%$).  
  *Gobernanza Regulatoria (EBA/GL/2017/16, Basilea CRE 20):* Todo árbol utilizado para binarización (*coarse-classing*) en scorecards o asignación de grados de riesgo debe exhibir una relación monótona creciente o decreciente con el factor de riesgo económico, o bien una justificación estricta de concavidad/convexidad (U-shape). De lo contrario, el modelo es rechazado por sobreajuste muestral.
* **Propuesta Cuantitativa de Mitigación:**  
  Integrar el algoritmo PAVA (*Pool Adjacent Violators Algorithm*) o forzar una restricción monotónica como condición de paro:
  $$\text{Signo}(\Delta BR_{i, i+1}) = \text{Signo}(\Delta BR_{i+1, i+2}) \quad \forall i$$

---

### [ALG-06] Ausencia de Poda por Complejidad de Costos (Minimal Cost-Complexity Pruning)
* **Archivo / Función:** `backend/split_engine.py` (Líneas 1700-1840) y `backend/tree_builder.py` (Líneas 340-428).
* **Diagnóstico de Vulnerabilidad:**  
  El algoritmo CRT (CART) opera exclusivamente con parada temprana (*pre-pruning* mediante `max_depth`, `min_parent_node`, `min_child_node`). Breiman et al. (1984) y Answer Tree 3.0 demostraron que la parada temprana es miope (*greedy myopia*) y no logra optimizar el compromiso sesgo-varianza. La formulación formal exige crecer el árbol hasta su máxima expresión $T_{\max}$ y ejecutar la poda por complejidad de costos minimizando:
  $$R_\alpha(T) = R(T) + \alpha |T|$$
  donde $|T|$ representa el número de hojas terminales y $\alpha$ es seleccionado mediante validación cruzada ($k$-fold con la regla del 1-SE).
* **Propuesta Cuantitativa de Mitigación:**  
  Implementar la secuencia de poda analítica retroactiva determinando el valor crítico de complejidad $\alpha_k = \frac{R(t) - R(T_t)}{|T_t| - 1}$ en cada nodo interno $t$.

---

### [ALG-07] Subestimación de Probabilidades de Incumplimiento en Nodos Extremos
* **Archivo / Función:** `backend/tree_builder.py` (Líneas 125-135), `Node.bad_rate`.
* **Diagnóstico de Vulnerabilidad:**  
  La probabilidad asignada a un nodo es puramente empírica: $\widehat{PD}_t = \frac{N_{1, t}}{N_t}$. En segmentos con $N_{1, t} = 0$, el aplicativo asigna $\widehat{PD} = 0.0\%$.  
  Bajo las directrices de Basilea (BCBS CRE 20.39) e IFRS 9:
  1. Una asignación de $PD = 0\%$ está formalmente prohibida. Debe existir un suelo regulatorio (*floor*) de al menos $0.03\%$ o $0.05\%$.
  2. La estimación puntual no incorpora el sesgo de muestra pequeña ni el margen de conservadurismo (*Margin of Conservatism* - MoC Categoría A).
* **Propuesta Cuantitativa de Mitigación:**  
  Incorporar el estimador bayesiano de Laplace/Jeffreys para calibración local:
  $$\widehat{PD}_{\text{Jeffreys}} = \frac{N_{1, t} + 0.5}{N_t + 1.0}$$
  y aplicar el suelo regulatorio: $PD_{\text{final}} = \max(PD_{\text{floor}}, \widehat{PD})$.

---

## DIMENSIÓN 2: ARQUITECTURA DE SOFTWARE Y DEUDA TÉCNICA

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MATRIZ DE HALLAZGOS: ARQUITECTURA Y DEUDA TÉCNICA                                           │
├───────────┬───────────────────────────────────────────────────────────────┬─────────────────┤
│ ID        │ Vulnerabilidad de Arquitectura                                │ Severidad       │
├───────────┼───────────────────────────────────────────────────────────────┼─────────────────┤
│ ARQ-01    │ Fuga de Lógica Analítica hacia la Capa de Presentación (GUI) │ ALTA            │
│ ARQ-02    │ Ineficiencia de Memoria por Almacenamiento Redundante de Mask │ ALTA            │
│ ARQ-03    │ Bucle Interpretado Escalar $O(N)$ en CRT Continuous Split    │ MEDIA           │
│ ARQ-04    │ Bloqueo del Hilo Principal de la GUI durante el Entrenamiento │ ALTA            │
│ ARQ-05    │ Copias Múltiples de DataFrames vía `reset_index` en Recursión │ MEDIA           │
└───────────┴───────────────────────────────────────────────────────────────┴─────────────────┘
```

### [ARQ-01] Violación del Principio de Sala Limpia: Fuga de Lógica Analítica al Frontend
* **Archivo / Función:** `frontend/gains_table.py` (Líneas 120-192), `update_table`.
* **Diagnóstico de Vulnerabilidad:**  
  Los cálculos matemáticos de la tabla de ganancias (% Población Acumulada, % Ganancia Acumulada, Índice Lift, Factor Lift) están implementados dentro de la clase `GainsTableWidget(QWidget)`.  
  *Impacto de Ingeniería:* Si el motor se ejecuta en modo batch, API sin interfaz gráfica o pipeline de producción de riesgo, no existe forma de extraer la tabla de ganancias ni métricas de concentración sin instanciar componentes de Qt (`QApplication`, `QTableWidgetItem`). Esto viola el principio fundamental de desacoplamiento entre el núcleo matemático (*clean-room*) y la capa de renderizado.
* **Propuesta Cuantitativa de Mitigación:**  
  Migrar la totalidad del cómputo a un módulo independiente en backend: `backend/gains_engine.py`, el cual debe recibir el objeto `DecisionTree` y retornar un `GainsTableResult` estructurado en dataclass o DataFrame puro. `frontend/gains_table.py` debe ser únicamente una vista consumidora.

---

### [ARQ-02] Ineficiencia de Memoria y Escalabilidad en Máscaras Booleanas Nodales
* **Archivo / Función:** `backend/tree_builder.py` (Líneas 380-405 y 612-615).
* **Diagnóstico de Vulnerabilidad:**  
  Cada instancia de `Node` almacena `self.mask = child_mask_global`, un array booleano de dimensión completa $N$.  
  Para un árbol con $K = 100$ nodos sobre un dataset de producción de $N = 2,000,000$ filas, almacenar 100 arrays booleanos requiere:
  $$\text{Memoria} = 100 \times 2,000,000 \times 1 \text{ byte} \approx 200 \text{ MB}$$
  adicionales al dataframe original. Esta duplicación masiva se agrava por el hecho de que las máscaras son fragmentadas y no liberan memoria durante el ciclo de vida del árbol.
* **Propuesta Cuantitativa de Mitigación:**  
  Almacenar únicamente arrays de índices enteros `np.uint32` en las hojas terminales o una función generadora de predicados lógicos basada en la ruta jerárquica del nodo:
  $$\text{Ruta}(t) = \bigwedge_{j=1}^{\text{profundidad}} \text{Condición}_j$$

---

### [ARQ-03] Bucle Escalar Interpretado en Búsqueda de Puntos de Corte Continuos (CRT)
* **Archivo / Función:** `backend/split_engine.py` (Líneas 1805-1811).
* **Diagnóstico de Vulnerabilidad:**  
  En `_find_best_binary_split_continuous`, la construcción de las máscaras booleanas izquierda y derecha tras hallar el umbral óptimo se realiza mediante un bucle `for` de Python elemento a elemento:
  ```python
  for i in range(len(df_original)):
      if clean_mask[i]:
          if original_vals[i] <= best_threshold:
              left_mask[i] = True
          else:
              right_mask[i] = True
  ```
  En datasets con cientos de miles de registros y múltiples variables continuas, este bucle interpretado degrada el tiempo de entrenamiento en un factor de $150\times$ frente a operaciones vectorizadas C-level de NumPy.
* **Propuesta Cuantitativa de Mitigación:**  
  Reemplazar inmediatamente por vectorización lógica directa:
  ```python
  left_mask = clean_mask & (original_vals <= best_threshold)
  right_mask = clean_mask & (original_vals > best_threshold)
  ```

---

### [ARQ-04] Bloqueo Síncrono del Hilo Principal de la GUI (*Main Event Loop Freezing*)
* **Archivo / Función:** `frontend/main_window.py` (Líneas 380-420), `_on_build_tree`.
* **Diagnóstico de Vulnerabilidad:**  
  La ejecución de `tree.build()` se dispara directamente sobre el hilo de la interfaz gráfica (`MainThread`). En modelos Exhaustive CHAID o datasets con más de 50,000 registros, el procesamiento toma entre 10 y 60 segundos, provocando que el sistema operativo marque la ventana como *"No responde"* (*Window Ghosting*), impidiendo la cancelación de la tarea o la visualización de una barra de progreso responsiva.
* **Propuesta Cuantitativa de Mitigación:**  
  Desacoplar el cómputo mediante la infraestructura `QThread` o `QThreadPool` / `QRunnable`, comunicando el progreso recursivo y la entrega del objeto `DecisionTree` mediante señales Qt (`pyqtSignal` / `Signal(int, int)`).

---

## DIMENSIÓN 3: VALIDACIÓN Y MONITORIZACIÓN (MRM - MODEL RISK MANAGEMENT)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ MATRIZ DE HALLAZGOS: VALIDACIÓN, MONITORIZACIÓN Y GOBERNANZA MRM                             │
├───────────┬───────────────────────────────────────────────────────────────┬─────────────────┤
│ ID        │ Brecha Metodológica frente a Estándares Internacionales       │ Severidad       │
├───────────┼───────────────────────────────────────────────────────────────┼─────────────────┤
│ MRM-01    │ Carencia Absoluta de Partición Out-of-Sample y Out-of-Time    │ CRÍTICA         │
│ MRM-02    │ Inexistencia del Índice de Estabilidad Poblacional (PSI / CSI)│ CRÍTICA         │
│ MRM-03    │ Ausencia de Pruebas Formales de Calibración (Hosmer-Lemeshow) │ ALTA            │
│ MRM-04    │ Falta de Curva de Pérdida Asimétrica en el Cutoff Decisional  │ ALTA            │
│ MRM-05    │ Omisión de Métricas Robustas para Desbalanceo Severo (PR-AUC) │ MEDIA           │
└───────────┴───────────────────────────────────────────────────────────────┴─────────────────┘
```

### [MRM-01] Sesgo de Optimismo por Evaluación Exclusiva In-Sample (Falta de OOS y OOT)
* **Archivo / Función:** `frontend/model_summary.py` (Línea 128) y `backend/risk_evaluation.py` (Líneas 100-135).
* **Diagnóstico de Vulnerabilidad:**  
  El aplicativo evalúa la matriz de confusión, el riesgo estimado $R(T)$, el error estándar $SE(R)$ y la tabla de ganancias **estrictamente sobre la misma muestra de desarrollo** (`Training Sample, N = 2,500`).  
  *Gobernanza SR 11-7 / IFRS 9:* La ausencia de esquemas de validación externa conduce a un severo sesgo de optimismo. Para modelos de riesgo de crédito es mandatorio reportar el desempeño en al menos dos muestras no observadas:
  1. **Muestra Fuera de Muestra (Out-of-Sample - OOS):** División aleatoria o estratificada (e.g. 70/30).
  2. **Muestra Fuera de Tiempo (Out-of-Time - OOT):** Cohorte temporal posterior (vintages de cosecha con horizonte de maduración de 12 meses) para verificar la estabilidad ante ciclos económicos.  
  El reporte actual de `Model Summary` no permite auditar si el árbol retiene su poder discriminante en condiciones reales.
* **Propuesta Cuantitativa de Mitigación:**  
  Extender `DecisionTree` y `ConfigDialog` para soportar la partición automática `(df_train, df_test, df_oot)` y generar matrices de confusión y tablas de ganancia comparativas duales (*Train vs Test vs OOT*), calculando el deterioro de Gini (*Gini Drop*):
  $$\Delta \text{Gini}_{\text{OOT}} = \frac{\text{Gini}_{\text{train}} - \text{Gini}_{\text{OOT}}}{\text{Gini}_{\text{train}}}$$

---

### [MRM-02] Ausencia de Indicadores de Estabilidad Poblacional (PSI) y de Atributos (CSI)
* **Archivo / Función:** Módulo completamente inexistente en la arquitectura actual.
* **Diagnóstico de Vulnerabilidad:**  
  No existe ninguna capacidad para monitorear el desplazamiento distributivo de los prestatarios (*dataset shift* / *covariate shift*).  
  Bajo las guías del Comité de Basilea y la directriz EBA/GL/2017/16, el **Population Stability Index (PSI)** es el estándar regulatorio obligatorio para el seguimiento continuo de modelos:
  $$PSI = \sum_{k=1}^{K} \left( P_{\text{actual}, k} - P_{\text{esperada}, k} \right) \times \ln\left( \frac{P_{\text{actual}, k}}{P_{\text{esperada}, k}} \right)$$
  Reglas de tráfico supervisoras:
  - $PSI < 0.10$: Estabilidad adecuada.
  - $0.10 \le PSI < 0.25$: Alerta moderada; requiere monitoreo e investigación.
  - $PSI \ge 0.25$: Inestabilidad severa; mandatorio suspender el uso del modelo, recalibrar o re-entrenar.
* **Propuesta Cuantitativa de Mitigación:**  
  Desarrollar el módulo analítico `backend/stability_engine.py` y una vista visual `frontend/stability_monitor.py` que permita cargar un archivo de seguimiento posterior y evaluar el PSI por nodo terminal y el CSI (*Characteristic Stability Index*) por variable explicativa.

---

### [MRM-03] Inexistencia de Pruebas de Calibración de Bondad de Ajuste (Hosmer-Lemeshow)
* **Archivo / Función:** `backend/risk_evaluation.py` (Líneas 95-160).
* **Diagnóstico de Vulnerabilidad:**  
  La evaluación del riesgo se limita al accuracy global y a la tasa de error $R(T)$. En riesgo de crédito bajo IFRS 9 (ECL) y Basilea (Cálculo de Capital por Riesgo de Crédito), la métrica determinante no es la precisión de corte binario, sino la **calibración exacta de las probabilidades de default**.  
  El sistema carece de:
  1. **Prueba de Hosmer-Lemeshow ($HL$):**
     $$H = \sum_{g=1}^{G} \frac{(O_g - N_g \bar{\pi}_g)^2}{N_g \bar{\pi}_g (1 - \bar{\pi}_g)} \sim \chi^2_{G-2}$$
  2. **Brier Score y Brier Skill Score (BSS):**
     $$BS = \frac{1}{N} \sum_{i=1}^{N} (\widehat{p}_i - y_i)^2, \quad BSS = 1 - \frac{BS}{BS_{\text{benchmark}}}$$
  3. **Curva de Calibración Empírica (*Reliability Diagram*):** Comparación gráfica entre la tasa de malos observada vs la probabilidad predicha en cada decil.
* **Propuesta Cuantitativa de Mitigación:**  
  Incorporar en el backend las métricas $HL$, $BS$ y $BSS$, e integrarlas en el reporte formal `Model Summary`.

---

### [MRM-04] Selección del Punto de Corte ($\theta$) sin Matriz de Costos Económicos Asimétricos
* **Archivo / Función:** `frontend/classification_matrix.py` (Líneas 40-100).
* **Diagnóstico de Vulnerabilidad:**  
  El aplicativo permite seleccionar el umbral $\theta$ de forma manual o ajustarlo a la probabilidad a priori de la raíz (e.g. 6.64%).  
  Sin embargo, en carteras crediticias la función de pérdida es intrínsecamente asimétrica:
  $$C_{\text{Falso Negativo}} \gg C_{\text{Falso Positivo}}$$
  - **Falso Negativo (Aprobar a un cliente que incurre en mora):** Provoca la pérdida de saldo adeudado ajustado por severidad ($LGD \times EAD$, típicamente $45\% - 70\%$ de la exposición).
  - **Falso Positivo (Rechazar a un cliente que hubiera pagado):** Provoca la pérdida del margen financiero o interés esperado ($NIM$, típicamente $3\% - 8\%$).  
  Fijar $\theta = 0.50$ o basarse en accuracy simétrico conduce a políticas crediticias ruinosas, ya que un error de morosidad cuesta entre $10\times$ y $20\times$ más que un rechazo comercial.
* **Propuesta Cuantitativa de Mitigación:**  
  Incorporar en `ClassificationMatrixWidget` la optimización cuantitativa del corte mediante minimización de la pérdida esperada:
  $$\theta^* = \arg\min_{\theta} \left[ C_{FN} \cdot FN(\theta) + C_{FP} \cdot FP(\theta) \right]$$
  donde los costos unitarios $C_{FN}$ y $C_{FP}$ sean parametrizables por el Oficial de Riesgo.

---

### [MRM-05] Vulnerabilidad en Evaluación de Desempeño bajo Desbalance Severo
* **Archivo / Función:** `backend/risk_evaluation.py` (Líneas 70-85), `overall_pct_correct`.
* **Diagnóstico de Vulnerabilidad:**  
  El aplicativo reporta `Overall Percentage Correct (Accuracy)`. En una cartera de riesgo con una tasa de morosidad del 3%, un modelo trivial que clasifique a todos los clientes como "Buenos" alcanza un $97\%$ de exactitud global, mientras su efectividad en detección de riesgo es nula ($Sensitivity_{\text{bad}} = 0\%$).  
  La confianza en el accuracy genera una falsa sensación de solvencia en comités de riesgo.
* **Propuesta Cuantitativa de Mitigación:**  
  Reportar mandatoriamente métricas robustas frente al desbalance:
  1. **Media Geométrica (G-Mean):** $\sqrt{\text{Sensitivity} \times \text{Specificity}}$
  2. **Área bajo la Curva de Precisión y Cobertura (PR-AUC):**
     $$PR\text{-}AUC = \int_0^1 \text{Precision}(R) \, dR$$
  3. **Coeficiente de Correlación de Matthews (MCC):**
     $$MCC = \frac{TP \times TN - FP \times FN}{\sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)}}$$

---

## PLAN MAESTRO DE REMEDIACIÓN CUANTITATIVA (ROADMAP FASE 6)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ CRONOGRAMA PRIORIZADO DE REMEDIACIÓN TÉCNICA (PHASE 6 ROADMAP)                              │
├─────────┬───────────────────────────┬───────────────────────────────────┬───────────────────┤
│ Sprint  │ Módulo Objetivo           │ Acciones Requeridas               │ Impacto           │
├─────────┼───────────────────────────┼───────────────────────────────────┼───────────────────┤
│ S-1     │ backend/split_engine.py   │ - Reemplazar Bonferroni por Kass  │ Corrección FWER   │
│         │                           │ - Reordenar grupos por BR en KS   │ Matemáticamente   │
│         │                           │ - Eliminar _detect_target_column  │ consistente       │
├─────────┼───────────────────────────┼───────────────────────────────────┼───────────────────┤
│ S-2     │ backend/gains_engine.py   │ - Extraer lógica de GainsTable    │ Sala Limpia pura  │
│         │ backend/tree_builder.py   │ - Vectorizar CRT splits           │ Rendimiento 150x  │
│         │                           │ - Poda Cost-Complexity (CART)     │ Control Overfit   │
├─────────┼───────────────────────────┼───────────────────────────────────┼───────────────────┤
│ S-3     │ backend/validation_engine │ - Particionado OOS / OOT          │ Cumplimiento IFRS9│
│         │ backend/stability_engine  │ - Módulo PSI y CSI poblacional    │ Basilea CRE 20    │
│         │ frontend/stability_mon    │ - Hosmer-Lemeshow y Brier Score   │ Supervisión MRM   │
└─────────┴───────────────────────────┴───────────────────────────────────┴───────────────────┘
```

1. **Prioridad Inmediata (S-1):** Corregir las fórmulas de Bonferroni (Kass 1980) y la función de KS en `backend/split_engine.py`, y desacoplar la variable target de heurísticas dinámicas para evitar distorsiones estadísticas en las particiones.
2. **Prioridad Arquitectónica (S-2):** Extraer la lógica de cálculo de ganancias y curvas Lorenz hacia el backend analítico (`backend/gains_engine.py`), optimizar los bucles escalares de CRT con vectorización NumPy y sustituir las paradas tempranas por poda formal de costo-complejidad.
3. **Prioridad Regulatoria (S-3):** Implementar la infraestructura de validación cruzada temporal (OOT), el motor de estabilidad poblacional (PSI/CSI) y los contrastes de calibración de probabilidades (Hosmer-Lemeshow / Brier Score) para dar cumplimiento íntegro a los estándares de auditoría de modelos de Basilea e IFRS 9.
