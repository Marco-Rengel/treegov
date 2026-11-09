# TreeGov — Diseño Fase 2: i18n y gobernanza GUI (post-Fase 7)

- **Estado:** ✅ Cerrada (02/11/2026). As-built verificado contra `frontend_v3/ecl_dialog.py`, `frontend_v3/scoring_dialogs.py`, `frontend_v3/main_window.py`, `frontend_v3/wizard.py` y `tests/test_ecl_dialog.py`, `tests/test_scoring_dialogs.py`, `tests/test_gui_smoke.py`, `tests/test_wizard.py` (suite 575/575).
- **Fecha:** 2026-11-02.
- **Origen:** backlog de zonas grises registrado en `docs/roadmap.md` (sección Deferred, subsección "⏳ Backlog post-Fase 7 — Zonas grises detectadas el 02/11/2026") tras la auditoría forense del 02/11/2026 (`docs/audit_log.md`, entrada "Auditoría forense post-Fase 7 y registro del backlog de zonas grises").
- **Alcance:** 7 deudas de GUI (T5, T6, T7, T8, T9, T10, T15) sobre 4 módulos de `frontend_v3/` y sus tests. Diseño gemelo de `docs/scripts_design.md` (Fase 1).

## §0. Contexto y alcance

La Fase 2 cierra la parte del backlog post-Fase 7 que vive en la capa de presentación: la retraducción en caliente y la gobernanza visible. El contrato de i18n del repo está bien definido para los paneles —`MetricsPanel`, `ReportsPanel` y `DataViewer` implementan `retranslate_ui()`, conectan `language_bus.language_changed` en `__init__` y desconectan al morir el widget—, pero tres diálogos (§1, §2) quedaron fuera de ese régimen y conservan literales en español que no cambian al conmutar el idioma. A eso se suma que el HUD no tiene un punto único de entrada para el modo de gobernanza y que la confirmación de poda es el último texto BANKING sin pasar por `tr()`.

Deudas cubiertas y evidencia en el código actual:

| ID | Deuda | Evidencia (estado actual) |
|----|-------|---------------------------|
| T5 | `ECLDialog` sin i18n ni `retranslate_ui`; el test congela literales ES | `frontend_v3/ecl_dialog.py:85` fija `setWindowTitle("Cálculo ECL")`; literales ES en `:101`, `:104`, `:111`, `:113`, `:118`, `:139`, `:141`, `:171`, `:218-222`. `tests/test_ecl_dialog.py:75` aserta `"Etapa 1"`, `"Etapa 2"`, `"Etapa 3"` |
| T6 | `BatchScoringDialog` y `ChampionChallengerDialog` sin `retranslate_ui` ni `language_bus` | `frontend_v3/scoring_dialogs.py:34` importa solo `tr`; ninguna de las dos clases define `retranslate_ui` |
| T7 | `BatchWorker.progress` es una señal muerta | Declarada en `frontend_v3/scoring_dialogs.py:58` (`progress = Signal(int)`); no existe ningún `.progress.emit(...)` ni `.progress.connect(...)` en el repo |
| T8 | El combo de motores omite `CHAID_EXHAUSTIVE`; `n_groups` y `challenger_params` no se exponen | `frontend_v3/scoring_dialogs.py:314` (`addItems(["CRT", "CHAID", "QUEST"])`); el backend ya soporta el motor (`backend_v3/session_state.py:75`) y ambos parámetros (`compare_champion_challenger(..., challenger_params=None, n_groups=10)`, `:1267` y `:1271`) |
| T9 | El HUD no tiene `set_governance_mode`; RESEARCH sin cobertura en paneles | `frontend_v3/main_window.py:909` y `:985` escriben el código crudo (`cfg["governance_mode"]`) en `_hud_lbl_gov_mode`; `ReportsPanel.set_governance_mode` (`:400`) y `MetricsPanel.set_governance_mode` (`:81`) no tienen ningún test que los invoque con `"RESEARCH"` |
| T10 | `_on_tree_context_menu` confirma la poda BANKING con texto ES hardcodeado | `frontend_v3/main_window.py:1186-1191`: título `"Prune Branch"` y mensaje `f"Podar la rama del nodo {node_id}: ..."` sin `tr()` |
| T15 | `step2_subtitle` afirma "binary target" con target K≥3 | Clave única `step2_subtitle` (`frontend_v3/i18n.py:102` EN / `:572` ES) fijada en `frontend_v3/wizard.py:703`; no existe `step2_subtitle_multiclass` |

**Fuera de alcance.** No entran en la Fase 2: T11 (`_last_train_params` sin `max_depth`, contrato D9) ni los hallazgos de backend N1 (`target_type` fuera del fingerprint) y N2 (`_rates_cls` con K=2), que se resuelven en un bloque de backend propio; los hallazgos documentales T1-T3, T12-T14, N3-N5 y N8; y las deudas de tests de error de diálogos N6 (`_on_error` / `_on_worker_failed` sin cobertura) y N7 (mocks de `BatchWorker`/`CCWorker`), que quedan registradas en el backlog para un bloque de tests posterior. La Fase 2 añade tests de comportamiento i18n y de RESEARCH (§5), no de rutas de excepción.

**Conciliación de numeración.** El plan de resolución registrado en el `audit_log` del 02/11/2026 describe este trabajo como "bloques 4–5" de 8; la numeración de sub-fases de este documento (`2.b.1` … `2.f.1`) es la nomenclatura de fase. Ambos vocabularios designan el mismo alcance: bloques 4–5 ⇔ Fase 2.

Tres reglas gobiernan el diseño:

1. **`tr()` no tiene fallback.** `frontend_v3/i18n.py:987` lanza `KeyError` para una clave desconocida y `:982` valida el idioma. Por tanto toda clave nueva se añade simultáneamente a `en` y `es`; una clave en un solo idioma es un fallo en tiempo de ejecución, no un texto en blanco.
2. **Sala limpia.** El frontend solo recoge parámetros y pinta DTOs planos. El parseo de `challenger_params` (§2) es estrictamente cadena→diccionario: ninguna validación estadística se mueve a la GUI.
3. **Cero literales visibles.** Tras la Fase 2, ningún texto que vea el usuario se escribe inline salvo los códigos de dominio (`BANKING`, `RESEARCH`, `CRT`, `CHAID`, `QUEST`, `CHAID_EXHAUSTIVE`), el marcador de dato ausente `"—"` y los nombres de fichero.

**Documentos de referencia.** `docs/3.11_gui_design_system.md` (contrato as-built de tokens, tipografía y tablas; la REGLA CRÍTICA 4.1.1 de Ctrl+C → TSV se respeta sin cambios), `docs/scripts_design.md` (diseño gemelo de la Fase 1), `docs/design_decisions.md` §22 (IFRS 9/ECL, terminología del diálogo ECL), `CONVENTIONS.md` (§Tests, §Caja blanca).

## §1. i18n en ECLDialog (T5)

**Problema.** `ECLDialog` mezcla dos regímenes: algunos textos pasan por `tr()` (`scoring_btn_browse` en `:93`, `scoring_csv_filter` en `:173`, `msg_error_title` en `:243`) y el resto está congelado en español. El resultado es un diálogo bilingüe a medias: en modo EN el título y las etiquetas siguen en español, y el test `test_ecl_dialog_table_population` convierte ese defecto en contrato al asertar sobre literales ES.

**Contrato.**

1. `ECLDialog.retranslate_ui()` público, sin argumentos, que reasigna **todos** los textos visibles: título de ventana, captions del formulario, cabeceras de la tabla, botones y filas de resultados cacheados. Se invoca al final de `__init__` (primera pintura y conmutación comparten un único camino, mismo idioma que `MainWindow.retranslate_ui`, `main_window.py:124`).
2. Conexión en `__init__`: `language_bus.language_changed.connect(self.retranslate_ui)`, tras construir los widgets.
3. Desconexión en `closeEvent`, con guarda `try/except RuntimeError` (el patrón de `prune_dialog.py:168-174`); `reject()` está sobrescrito (`ecl_dialog.py:249`) para bloquear el cierre con worker activo, y `done()` no dispara `closeEvent`, así que la desconexión se centraliza en un helper idempotente `_detach_bus()` que invocan tanto `closeEvent` como `done()`.
4. Las captions del formulario dejan de pasarse como `str` a `form.addRow(...)` (Qt crea un `QLabel` interno no recuperable) y pasan a ser `QLabel` explícitos guardados como atributos, para poder reasignarles texto en `retranslate_ui`.
5. La tabla de resultados se re-renderiza desde un DTO cacheado: `_on_finished` guarda `self._last_result = result` y delega en `_render_result()`; `retranslate_ui` re-invoca `_render_result()` si hay caché. Sin caché, un cambio de idioma dejaría las cinco filas en el idioma anterior, que es exactamente el defecto que T5 describe.

**Mapeo literal → clave** (todas existentes salvo las dos marcadas como nuevas):

| Literal actual | Clave i18n | Nota |
|----------------|-----------|------|
| `"Cálculo ECL"` (`:85`) | `ecl_dlg_title` | Cambio visible buscado: ES pasa a "Cálculo IFRS 9 / ECL" y EN deja de mostrar español |
| `"CSV de entrada"` (`:101`) | `ecl_input_csv` | |
| `"Columna de PD"` (`:104`) | `ecl_pd_col` | |
| `"Tasa EIR"` (`:111`) | `ecl_eir` | |
| `"Aplicar descuento"` (`:113`) | `ecl_apply_eir` | |
| `["Métrica", "Valor"]` (`:118`) | `ecl_col_metric`, `ecl_col_value` | Cabeceras reasignadas en `retranslate_ui` |
| `"Cancelar"` (`:139`) | `wizard_cancel` | Reutilizada; no se duplica |
| `"Calcular"` (`:141`) | `ecl_btn_calculate` | **Nueva** (EN "Calculate") |
| `"Seleccionar CSV de entrada"` (`:171`) | `ecl_input_dialog_title` | **Nueva** (EN "Select scoring CSV"); no se reutiliza `batch_input_dialog_title` para no arrastrar la semántica "input" del batch |
| `"ECL 12m"`, `"ECL Lifetime"` (`:218-219`) | `ecl_total_12m`, `ecl_total_lifetime` | Filas del DTO |
| `"Etapa 1"`, `"Etapa 2"`, `"Etapa 3"` (`:220-222`) | `ecl_stage_1`, `ecl_stage_2`, `ecl_stage_3` | Filas del DTO |

**Consecuencias.** El diálogo queda con un único idioma visible en todo momento. `tests/test_ecl_dialog.py::test_ecl_dialog_table_population` debe asertar sobre `tr("ecl_total_12m")` etc. en lugar de sobre literales: es la única modificación de un test existente en toda la Fase 2 y se justifica porque el test congela el bug (invariante §6-6). Se añade `test_ecl_dialog_retranslate`, que construye el diálogo en EN, emite `language_bus.language_changed("es")` y verifica título, captions, cabeceras, botones y las cinco filas ya cacheadas.

## §2. i18n en BatchScoringDialog y ChampionChallengerDialog (T6, T7, T8)

**Problema.** Los dos diálogos de scoring usan `tr()` para las etiquetas construidas en el momento de crear el formulario y para los `QMessageBox`, pero carecen de `retranslate_ui()` y de conexión al bus: cualquier cambio de idioma con el diálogo vivo deja la ventana en el idioma de apertura. Además, los combos muestran códigos crudos (`"exclude"`, `"error"`, `"majority"`, `:169` y `:324`; `"CRT"`, `"CHAID"`, `"QUEST"`, `:314`), `BatchWorker.progress` (`:58`) nunca se emite, y el diálogo Champion-Challenger no permite elegir `CHAID_EXHAUSTIVE` ni ajustar `n_groups` o `challenger_params` aunque el backend ya los acepte.

**Contrato T6 — retraducción.**

1. `BatchScoringDialog.retranslate_ui()` y `ChampionChallengerDialog.retranslate_ui()`, con la misma disciplina que §1: invocación al final de `__init__`, conexión al bus tras construir los widgets, desconexión vía `_detach_bus()` en `closeEvent` y `done()`. La desconexión en `done()` no es opcional: `BatchScoringDialog` cierra con `self.accept()` al terminar el lote (`:266`), que no pasa por `closeEvent`.
2. Captions del formulario como `QLabel` atributo (misma razón que §1-4), para que `retranslate_ui` pueda reasignar texto sin reconstruir el `QFormLayout`.
3. Combos con doble representación: el código canónico vive en `itemData(Qt.UserRole)` y el texto visible es su etiqueta traducida. `_execute` lee `currentData()` en lugar de `currentText()` (`:419` motor, `:422` política; `:256` política del batch). El valor enviado al backend no cambia: la paridad de §6-2 depende de que el código siga siendo exactamente `CRT` / `CHAID` / `CHAID_EXHAUSTIVE` / `QUEST` y `exclude` / `error` / `majority`.
4. Etiquetas de motor: se promueve `_ENGINE_LABELS` de `frontend_v3/wizard.py:74` a constante pública `ENGINE_LABELS` (alias privado conservado) y se importa desde `scoring_dialogs`. Es el único mapeo de motores del frontend y evita una segunda tabla que derive. Etiquetas de política: tres claves nuevas (`unseen_policy_exclude`, `unseen_policy_error`, `unseen_policy_majority`).

**Contrato T7 — eliminar la señal muerta.** Se borra `progress = Signal(int)` de `BatchWorker` (`scoring_dialogs.py:58`). No requiere migración: no hay `.emit` ni `.connect` en el repo, y la barra de progreso del diálogo es indeterminada por rango (`setRange(0, 0)` en `_set_running`, `:222`), no por señal. El test aserta la ausencia: `"progress" not in BatchWorker.__dict__`.

**Contrato T8 — combo completo y parámetros expuestos.**

1. El combo de motores del retador pasa a `CRT`, `CHAID`, `CHAID_EXHAUSTIVE`, `QUEST`, en el orden de `_ENGINES` (`wizard.py:68`). `CHAID_EXHAUSTIVE` ya es aceptado por el backend (`_ENGINE_FACTORIES`, `session_state.py:73-75`), por lo que T8 es una brecha exclusivamente de frontend.
2. `n_groups` como `QSpinBox` con rango 3-20 y default 10, espejo de los defaults del backend (`compare_champion_challenger`, `:1271`). El mínimo 3 replica la restricción de Hosmer-Lemeshow que el backend ya aplica internamente (`session_state.py:1168-1171`: `n_groups >= 3` y `n_groups * 5 <= N`); la GUI no recalcula nada, solo no ofrece valores imposibles.
3. `challenger_params` como `QLineEdit` con pares `clave=valor` separados por comas (p. ej. `max_depth=4,min_pop=50`). Parseo puro en el frontend: entero si el valor es entero, `float` si es decimal, cadena en otro caso; cadena vacía → `None` (sin override). Un par sin `=` o con clave vacía aborta antes de crear el worker y muestra `QMessageBox` con `msg_error_title` + la clave nueva `cc_params_invalid`.
4. `CCWorker.__init__` gana `n_groups: int` y `challenger_params: dict | None` y los reenvía como keyword arguments (la firma del backend es keyword-only: `session_state.py:1265-1271`).
5. Paridad: con `n_groups=10` y params vacíos, la llamada resultante es idéntica a la actual (`challenger_params=None`, `n_groups=10`), de modo que fingerprints y métricas del par campeón-retador no cambian (invariante §6-2).

**Consecuencias.** Los dos diálogos quedan completamente retraducibles y el retador alcanza la superficie que el backend ya ofrecía. Los tests `test_batch_dialog_creation`, `test_batch_dialog_run_mocked` y `test_cc_dialog_table_population` se conservan sin cambios de expectativa (los tres leen `_progress` y la tabla, no los textos); se añaden tests de retraducción y de combo/params en 2.c.1.

## §3. Gobernanza en HUD y confirmación de poda (T9, T10)

**Problema.** El HUD de gobernanza muestra hoy el código crudo del modo (`main_window.py:909`, `:985`) y no tiene un punto único de entrada: el modo se escribe a mano en `_on_wizard_finished` y en el flujo de inversión, y `retranslate_ui` reasigna las captions del grupo (`:215-217`) pero no el valor, que queda en el idioma del momento del entrenamiento. Los paneles `ReportsPanel` y `MetricsPanel` sí tienen `set_governance_mode`, pero se invocan inline (`:899-900`) y ningún test los ejercita con `"RESEARCH"`, de modo que la terminología RESEARCH (PD → "Probability", bad → "Event") está sin cobertura. Por último, la confirmación de poda manual es el único texto BANKING fuera de `tr()`.

**Contrato.**

1. `_build_hud_panel_content` (`:662`) pasa a ser el único lugar que construye el bloque de gobernanza, y `MainWindow.set_governance_mode(mode: str)` es el único punto de entrada que lo actualiza: guarda `self._governance_mode = mode` y pinta la etiqueta con `tr("step4_govmode_banking_short")` o `tr("step4_govmode_research_short")` (`i18n.py:199-200` / `:675-676`). El código crudo (`BANKING` / `RESEARCH`) sigue siendo el dato canónico y se conserva en el atributo para el log y para el fingerprint; solo cambia su representación visible.
2. `set_governance_mode` propaga el modo a `_reports_panel.set_governance_mode` y `_metrics_panel.set_governance_mode`, absorbiendo las dos llamadas inline de `:899-900`. Un solo camino, tres consumidores.
3. `_on_wizard_finished` (`:870`) invoca `self.set_governance_mode(cfg["governance_mode"])` en lugar de escribir `_hud_lbl_gov_mode` directamente. El `_mode_name` hardcodeado de `:889-891` (`"Banking"` / `"Research"`) pasa a las mismas claves cortas, con lo que `_lbl_mode` también sobrevive a una conmutación de idioma.
4. `retranslate_ui` re-renderiza el modo desde `self._governance_mode` (no desde un `QLabel` cacheado), de modo que captions y valor cambian juntos.
5. T10: la confirmación de poda usa `tr()` en título y cuerpo. Título: `menu_tree_prune_branch` (clave existente, `i18n.py:452` / `:928`). Cuerpo: clave nueva `prune_branch_confirm` con placeholder `{node_id}`, equivalente al texto actual, que se formatea con `.format(node_id=node_id)`. El resto del slot (habilitación de Grow/Prune por hoja, registro en el Manual Override Log, sufijo de fingerprint) no cambia: T10 es estrictamente un cambio de strings.

**Consecuencias.** El modo de gobernanza queda con una sola fuente de verdad visible y auditable, y la terminología RESEARCH de los paneles deja de ser código no verificado. Los tests de 2.d.1 y 2.e.1 cubren: `set_governance_mode("RESEARCH")` pinta etiqueta traducida en ambos idiomas; `MetricsPanel` y `ReportsPanel` reciben el modo y renderizan `tr_term` RESEARCH; la confirmación de poda contiene el id del nodo y no contiene `"Podar la rama"` en modo EN.

## §4. `step2_subtitle` dinámico (T15)

**Problema.** `PredictorsPage.retranslate_ui` (`wizard.py:701`) fija `tr("step2_subtitle")`, cuya redacción EN dice "Pick the **binary** target and at least one predictor" (`i18n.py:102`). Con un target de K≥3 clases el subtítulo miente, y el propio wizard conoce K: la tabla de clases se repuebla desde `target_provider` (`_refresh_class_table`, `wizard.py:537`) y `Session.describe_target` devuelve un diccionario `{valor: frecuencia}` (`session_state.py:225-252`) cuyo número de claves es exactamente K.

**Contrato.**

1. Dos claves nuevas: `step2_subtitle_multiclass` (EN "Pick the target (3+ classes) and at least one predictor." / ES equivalente) y `step2_subtitle_no_target` (EN "Pick a target and at least one predictor."), más la conservación de `step2_subtitle` para el caso K≤2.
2. `retranslate_ui` selecciona la clave mediante un helper `_subtitle_key()` que consulta el `target_provider` con el target seleccionado y cuenta claves del diccionario: K≥3 → `step2_subtitle_multiclass`; K≤2 → `step2_subtitle`; sin target, target vacío o excepción del provider (`ValueError`/`RuntimeError`, el mismo par que ya captura `_refresh_class_table` en `:563`) → `step2_subtitle_no_target`.
3. El subtítulo no se recalcula solo al conmutar idioma: se refresca también cuando cambia el target o se repuebla la tabla de clases (`_refresh_class_table` llama a la reasignación del subtítulo al final). Sin ese enganche, elegir un target multiclase dejaría el subtítulo anterior hasta el siguiente cambio de idioma.

**Consecuencias.** El texto deja de contradecir al dataset y el wizard gana una tercera redacción honesta para el estado inicial. Paridad: con K=2 la cadena visible es idéntica a la actual, así que ningún test existente de wizard cambia de expectativa.

## §5. Sub-fases y criterios de aceptación

| Sub-fase | Alcance | Criterio de aceptación | Archivos tocados |
|----------|---------|------------------------|------------------|
| 2.b.1 | T5: `ECLDialog.retranslate_ui`, bus conectado/desconectado, captions y tabla cacheadas, mapeo de §1 | Título, captions, cabeceras, botones y las cinco filas cambian con el idioma; `test_ecl_dialog_table_population` asertando sobre `tr(...)` pasa en EN y ES; suite sin regresiones | `frontend_v3/ecl_dialog.py`, `frontend_v3/i18n.py`, `tests/test_ecl_dialog.py` |
| 2.c.1 | T6 + T7 + T8: retraducción de ambos diálogos, borrado de `BatchWorker.progress`, `CHAID_EXHAUSTIVE` en el combo, `n_groups` y `challenger_params` | Ambas ventanas retraducen en caliente; `"progress" not in BatchWorker.__dict__`; el combo ofrece 4 motores y `currentData()` devuelve los códigos canónicos; `n_groups` y params llegan al backend (worker espiado) | `frontend_v3/scoring_dialogs.py`, `frontend_v3/wizard.py`, `frontend_v3/i18n.py`, `tests/test_scoring_dialogs.py` |
| 2.d.1 | T9 + T10: `set_governance_mode` en el HUD, propagación desde `_on_wizard_finished`, confirmación de poda con `tr()` | El HUD muestra la etiqueta localizada en ambos idiomas y conserva el código canónico en el atributo; la confirmación usa `prune_branch_confirm` con el id del nodo | `frontend_v3/main_window.py`, `frontend_v3/i18n.py`, `tests/test_gui_smoke.py` |
| 2.e.1 | T9 (cobertura): tests de RESEARCH en paneles | `set_governance_mode("RESEARCH")` en `MetricsPanel` y `ReportsPanel` renderiza la terminología RESEARCH (`tr_term`); BANKING sigue renderizando la bancaria; ambos idiomas | `tests/test_gui_smoke.py`, `tests/test_e2e_reports.py` (si el escenario lo permite sin red) |
| 2.f.1 | T15: subtítulo dinámico | K=2 → `step2_subtitle`; K≥3 → `step2_subtitle_multiclass`; sin target → `step2_subtitle_no_target`; el subtítulo se refresca al cambiar de target, no solo al cambiar de idioma | `frontend_v3/wizard.py`, `frontend_v3/i18n.py`, `tests/test_wizard.py` |

**Criterios transversales de aceptación** (aplican a las cinco sub-fases):

1. **Tests EN/ES pasan.** Cada sub-fase añade al menos un test que ejerce la ruta en inglés y en español, con `language_bus.language_changed.emit(lang)` como disparador real, no con llamadas directas a `retranslate_ui`.
2. **Paridad BANKING bit a bit.** Ninguna sub-fase altera fingerprints ni métricas: se reutilizan los valores dorados existentes de la suite. Cualquier diferencia de `params_fingerprint` en un escenario BANKING es un fallo de la sub-fase, no un cambio aceptable.
3. **Suite 567+.** Al abrir la Fase 2 la suite está en 567/567 (verificado el 02/11/2026). Ninguna sub-fase se commitea por debajo de 567 ni con regresiones; el conteo final as-built se fija al cerrar 2.f.1 y se propaga a `docs/estado_proyecto.md`, READMEs y `AGENTS.md`.
4. **Cero claves huérfanas.** Toda clave nueva existe en `en` y `es` en el mismo commit (invariante §6-4), y toda clave que quede sin uso se elimina en la misma sub-fase que la deja sin uso.

## §6. Invariantes

1. **Suite verde.** `python -m pytest tests -q` pasa en cada sub-fase; el suelo es 567 y nunca baja. Un test rojo no se commitea ni se marca como `xfail` para cerrar.
2. **Paridad BANKING bit a bit.** Los escenarios BANKING existentes producen el mismo `params_fingerprint` y las mismas métricas antes y después de la Fase 2. Ni la retraducción, ni el borrado de la señal muerta, ni los nuevos campos del retador pueden tocar el camino analítico: los cambios de §2-5 son no-op cuando los campos están en su default.
3. **Cero strings literales en UI.** Ningún texto visible se escribe inline salvo códigos de dominio, `"—"` y nombres de fichero. Al cerrar 2.f.1, un `grep` de literales ES en `frontend_v3/ecl_dialog.py`, `frontend_v3/scoring_dialogs.py` y el bloque de poda de `main_window.py` no devuelve coincidencias.
4. **Paridad de claves i18n.** `tr()` lanza `KeyError` ante una clave ausente (`i18n.py:987`): toda clave nueva se añade a los dos diccionarios en el mismo commit, y `set_language` solo acepta idiomas de `SUPPORTED` (`:990-997`).
5. **Frontend sin analítica.** El parseo de `challenger_params` es cadena→diccionario; ninguna validación estadística, de rangos de `n_groups` más allá del mínimo de presentación, ni de motores se implementa en la GUI. El backend sigue siendo la autoridad y sus errores llegan por `_on_worker_failed`.
6. **No se modifican tests existentes salvo congelación de bug.** La única excepción de la Fase 2 es `test_ecl_dialog_table_population`, que aserta literales ES y por tanto congela el defecto T5; se reescribe contra `tr(...)` en 2.b.1 y se documenta en el `audit_log`. El resto de tests existentes se conserva intacto y los nuevos son adiciones puras.
7. **Ciclo de vida del bus.** Todo widget que conecta `language_bus.language_changed` lo desconecta en su ruta de cierre, con guarda `try/except RuntimeError`, cubriendo tanto `closeEvent` como `done()` (accept/reject). Un diálogo destruido con la conexión viva es un fallo de la sub-fase.

## §7. As-built

Verificado el 02/11/2026 contra el código real:

- **T5** (`ecl_dialog.py`): `ECLDialog.retranslate_ui()` implementado; `_detach_bus()` idempotente en `closeEvent` y `done()`; `_report_dto` cacheado y repintado en `retranslate_ui`; claves nuevas `ecl_btn_calculate` y `ecl_input_dialog_title` en `i18n.py` (EN/ES).
- **T6** (`scoring_dialogs.py`): `BatchScoringDialog.retranslate_ui()` y `ChampionChallengerDialog.retranslate_ui()` implementados; `_detach_bus()` en ambos; combos con doble representación (`itemData` + texto traducido); `ENGINE_LABELS` importado desde `frontend_v3.wizard`.
- **T7**: `BatchWorker.progress` eliminada (no aparece en `scoring_dialogs.py`).
- **T8**: combo de motores del retador usa `ENGINE_LABELS` (4 motores, incluye `CHAID_EXHAUSTIVE`); `_n_groups_spin` (rango 3–20, default 10) y `_params_edit` con `_parse_challenger_params` (cadena→dict, entero/float/str) presentes; `CCWorker` propaga `n_groups` y `challenger_params`.
- **T9**: `MainWindow.set_governance_mode(mode)` propaga a `_reports_panel` y `_metrics_panel`; `retranslate_ui` re-renderiza desde `self._governance_mode`. Test `test_hud_research_mode` cubre el flujo en EN y ES.
- **T10**: `_on_tree_context_menu` usa `tr("menu_tree_prune_confirm_title")` y `tr("menu_tree_prune_confirm_body").format(node_id=node_id)`.
- **T15**: `PredictorsPage._subtitle_key()` selecciona `step2_subtitle_no_target` / `step2_subtitle_multiclass` / `step2_subtitle` según el conteo del `target_provider`. Test `test_wizard_multiclass_subtitle` cubre los tres casos.
