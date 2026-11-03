# TreeGov — Diseño Fase 1: Scripts de infraestructura (post-Fase 7)

- **Estado:** propuesto (pendiente de veredicto de auditoría de diseño).
- **Fecha:** 2026-11-02.
- **Origen:** backlog de zonas grises registrado en `docs/roadmap.md` (sección Deferred) tras la auditoría forense del 02/11/2026; entrada correspondiente en `docs/audit_log.md` ("Auditoría forense post-Fase 7 y registro del backlog de zonas grises").
- **Alcance:** 26 deudas del backlog (F1–F8, U1–U6, V1–V12 y P1–P4) sobre los tres scripts de `scripts/`.

## §0. Contexto y alcance

La Fase 1 resuelve la parte del backlog post-Fase 7 que vive en los scripts de infraestructura de `scripts/`. La auditoría del 02/11/2026 catalogó 26 deudas que la suite 561/561 no captura, porque los tres scripts se escribieron como utilería one-shot de la Fase 3.6 y quedaron fuera del régimen de calidad del resto del repo: sin tests, sin logging, con contratos implícitos, paths dependientes del cwd y fallos silenciosos. Esta fase los eleva a primera clase: contratos explícitos, errores visibles con exit codes distinguibles, idempotencia verificable, paths anclados a `__file__` y cobertura en pytest.

Los scripts cubiertos son `scripts/fetch_datasets.py` (F1–F8), `scripts/update_readme_date.py` (U1–U6) y `scripts/validate_uci.py` (V1–V12), más las deudas de proceso P1–P4. Queda fuera de este documento: todo lo relativo a GUI/i18n (bloques 4–5 del plan de resolución; diseño gemelo en `docs/gui_i18n_governance_design.md`, pendiente de creación en el bloque 4), los hallazgos transversales (T*) y los hallazgos de backend (`T11`, `N1`, `N2`), que se resuelven fuera de la Fase 1.

Tres reglas gobiernan el diseño:

1. **Sala limpia replicada por scripts.** La prohibición de sklearn/statsmodels/xgboost/lightgbm/catboost y la exigencia de cita bibliográfica para toda fórmula (`CONVENTIONS.md` §Caja blanca) aplican al código de la Fase 1; las fórmulas que los scripts reproducen viven ya citadas en `backend_v3/` y aquí solo se reutilizan con su cita.
2. **Sin red real en tests.** Ningún test de la Fase 1 abre sockets: `urllib.request.urlopen` se monkeypatchea siempre (§4, invariante §7-2).
3. **Errores visibles, no silenciosos.** Todo fallo detectable aborta con excepción o exit code distinguido; la degradación silenciosa a `None` está prohibida (V6).

## §1. fetch_datasets.py — F1–F8

### F1 — Idempotencia prometida no implementada

- **Problema.** El docstring promete ejecución idempotente, pero la implementación re-descarga los seis datasets en cada invocación, sin comprobar si el destino ya está al día.
- **Decisión.** Idempotencia por hash sidecar: para cada CSV final bajo `data/uci/` se mantiene un sidecar `<dataset>.sha256` (SHA-256 en hex minúsculas, FIPS 180-4) escrito tras cada descarga verificada. Si el target existe, su hash coincide con el sidecar y la URL fuente no cambió respecto al manifiesto, el dataset se salta con log INFO ("skip").
- **Consecuencias.** La segunda ejecución no toca la red para datasets vigentes; termina en tiempo de seis hashes, no de seis descargas, y el CI puede ejecutar fetch sin re-descargar. El ciclo de actualización del manifiesto queda definido en F7.

### F2 — Escribe en tests/fixtures/uci/ en lugar de data/uci/

- **Problema.** El script descarga hoy los CSV normalizados dentro del árbol de fixtures de pytest, mezclando la descarga viva con el material versionado de la Fase 3.6.
- **Decisión.** El destino canónico es `data/uci/<dataset>.csv`, resuelto contra la raíz del repo (F8). `tests/fixtures/uci/` queda como árbol de solo lectura: ni fetch ni validate escriben ahí. La guarda P4 (§5) bloquea cualquier resolución de ruta bajo `tests/fixtures/` intentada por los scripts.
- **Consecuencias.** Los fixtures versionados de pytest se congelan byte-a-byte (invariante §7-3) y las descargas frescas viven en `data/uci/`. La docstring del script se ajusta para no prometer fixtures.

### F3 — line.split(sep) en vez de csv.reader

- **Problema.** La normalización parte cada línea con `str.split` sobre el separador; un valor que contenga el separador desalinea columnas y produce CSV corruptos.
- **Decisión.** Lectura con `csv.reader` sobre el contenido decodificado (UTF-8) y escritura con `csv.writer`, con delimitador y quoting definidos por el manifiesto de cada dataset. El particionado manual desaparece: la semántica CSV la fija la librería estándar.
- **Consecuencias.** Los CSV normalizados son válidos para `Session.load_dataset` y para inspección externa aunque el dataset contenga el separador dentro de un valor. El historial de columnas desalineadas en car/balance/iris deja de existir.

### F4 — target_map={} silencioso en blood_transfusion

- **Problema.** El mapa de traducción del target llega vacío para blood_transfusion y el script lo tolera: termina sin mapear y los consumidores posteriores leen ruido.
- **Decisión.** Validación con `RuntimeError`: al completar el mapeo de cada dataset se verifican los valores crudos observados del target contra el mapa; si queda cualquier valor sin mapear, o el mapa está vacío para un dataset que declara target en el manifiesto, el script aborta con `RuntimeError` que nombra el dataset y el valor sin mapear.
- **Consecuencias.** El mapeo fallido se descubre en el primer minuto de ejecución, no más tarde en un E2E. El mapa de blood_transfusion se completa con sus clases binarias (1 = donor, 2 = non_donor), coherentes con el diseño 3.6.

### F5 — Sin logging estructurado

- **Problema.** El script emite prints sueltos: no hay niveles, ni timestamps, ni una forma greppable de distinguir advertencias de fallos.
- **Decisión.** Se usa la librería estándar `logging`, configurada desde un helper compartido en `scripts/` (una única configuración, no inline en cada script): formato `%(asctime)s %(levelname)s %(name)s %(message)s`, nivel por flag `--log-level` con default INFO, stream en stderr. Los mensajes son de una línea, con ID de dataset y SHA; cada evento download/skip/verify/write deja su registro.
- **Consecuencias.** El flujo de una ejecución es auditable y filtrable por grep; un WARNING convive con el resto del log sin destruirlo. Los tests de §4 aserten sobre `caplog`, no sobre stdout.

### F6 — Sin reintentos en urlopen

- **Problema.** Un fallo transitorio de UCI aborta toda la descarga y obliga a relanzar el script a mano.
- **Decisión.** Reintentos con backoff exponencial y techo: 3 intentos totales por URL (t=0, +2 s, +4 s), solo sobre errores transitorios (`URLError`, `HTTPError` 5xx/429, `socket.timeout`). Un `HTTPError` 4xx determinista (403/404) no se reintenta: aborta de inmediato. En tests, `time.sleep` se monkeypatchea: el backoff nunca duerme de verdad (§7-2).
- **Consecuencias.** La descarga tolera picos de la red de UCI sin abortar por un único fallo transitorio. La política de intentos y delays queda documentada en la docstring del helper, accesible con `--help`.

### F7 — Workflow de actualización de hashes no documentado

- **Problema.** Los SHA-256 esperados están fijados en el manifiesto del script sin un protocolo documentado: nadie sabe cómo actualizarlos cuando una fuente cambia.
- **Decisión.** El manifiesto (URL, SHA-256 esperado, sidecar de F1, target_map de F4) queda como constante del script y su ciclo de vida se documenta aquí: actualizar la URL → relanzar fetch con `--refresh-hash` (graba el SHA observado en el sidecar y reporta la diferencia) → revisión humana del commit que cambia el manifiesto.
- **Consecuencias.** Ningún commit de manifiesto es irreproducible: el revisor puede reproducir el SHA observado con el mismo script. El drift de una fuente queda visible como diff del sidecar.

### F8 — Rutas relativas al cwd

- **Problema.** Los destinos de descarga y el manifiesto se resuelven relativos al cwd: ejecutado desde otra carpeta, el script descarga en un lugar equivocado.
- **Decisión.** Todas las rutas se resuelven contra `pathlib.Path(__file__).resolve().parents[1]` (raíz del repo) y se declaran como constantes `REPO_ROOT / "data" / "uci"`.
- **Consecuencias.** Desaparece la clase de bug "funciona solo si lo ejecutas desde la raíz"; el script es válido invocado desde la raíz, desde `scripts/` o con un cwd arbitrario, y el test de §4 aserta esa propiedad.

## §2. update_readme_date.py — U1–U6

### U1 — Fallo silencioso si el regex no matchea

- **Problema.** Si un README cambia el formato de fecha (se mueve el bloque, cambia el marcador), el regex deja de matchear, el script no reemplaza nada y termina en exit 0.
- **Decisión.** Si el regex no matchea contra un README objetivo, el script lanza `RuntimeError` que incluye la ruta del archivo y el patrón exacto usado, y aborta con exit ≠ 0. Los patrones y el marcador 📅 viven en constantes de cabecera, no inline en el flujo.
- **Consecuencias.** Un cambio de formato de README se detecta la primera vez que se ejecuta el script, no la segunda vez que alguien nota la fecha stale. El test de §4 congela el contrato "RuntimeError con ruta y patrón".

### U2 — No atómico entre README.md y README.es.md

- **Problema.** Una falla a mitad de ejecución puede dejar los dos READMEs con fechas divergentes: uno escrito y el otro no.
- **Decisión.** Ambos renders se producen primero en memoria y se verifican las dos correspondencias de regex antes de tocar disco. Después cada target se escribe a un archivo temp del mismo directorio, con flush y rename atómico. Si un rename falla tras haber aplicado el otro, el script restaura desde el contenido previo (leído al inicio) y aborta.
- **Consecuencias.** Tras un fallo, ambos READMEs quedan o ambos en el valor previo o ambos en el nuevo: la divergencia entre los dos no es un estado posible. El test de §4 simula el fallo del segundo rename y verifica que no queda divergencia.

### U3 — Solo actualiza fechas marcadas con 📅

- **Problema.** Fechas de diagramas sin el marcador 📅 quedan stale: la actualización depende de recordar colocar los marcadores.
- **Decisión.** El marcador 📅 se documenta como contrato canónico del workflow (no se elimina: es el opt-in explícito que evita tocar fechas históricas de changelogs). La regla "toda fecha de estado corriente de release va marcada con 📅 en ambos READMEs, cabecera y diagrama Mermaid" queda escrita en el docstring del script; los targets se declaran por constantes.
- **Consecuencias.** La deuda U3 se transforma de bug a contrato: el script no inventa targets ni descubre archivos en runtime. Una fecha stale futura se mitiga marcando el release, no adivinando posiciones en el HTML.

### U4 — Sin --check / dry-run

- **Problema.** El script solo tiene modo de mutación: no hay forma de preguntar si los READMEs están al día sin escribir.
- **Decisión.** Dos modos: default (muta) y `--check` (no escribe). `--check` calcula la fecha candidata y la compara con la vigente por archivo; si hay pendiente, imprime `ruta: vigente → candidata` y termina con exit 1; si todo está al día, exit 0.
- **Consecuencias.** `--check` es usable en CI o en un hook de commit como detección temprana. Los dos tests del contrato (al día exit 0, desactualizado exit 1) viven en §4.

### U5 — Sin guarda de retroceso temporal

- **Problema.** Nada impide escribir una fecha anterior a la vigente, regresando el metadato de release.
- **Decisión.** Guarda de retroceso: antes de escribir, la fecha vigente del README se compara con la candidata (hoy por defecto, o `--date <YYYY-MM-DD>`); si la candidata es anterior a la vigente, aborta con `RuntimeError("retroceso temporal en <ruta>: <vigente> → <candidata>")`.
- **Consecuencias.** Un commit que arrastre un README viejo no puede retroceder la fecha de release. En tests el caso se ejercita con `--date` explícita, sin depender del calendario.

### U6 — Path anclado a scripts/

- **Problema.** Las rutas objetivo se resuelven ancladas al directorio `scripts/` del archivo, no a la raíz del repo: el contrato era frágil si el script se movía.
- **Decisión.** El script resuelve la raíz del repo desde `__file__` (`Path(__file__).resolve().parents[1]`), no desde el cwd, y ambos targets se declaran como `REPO_ROOT / "README.md"` y `REPO_ROOT / "README.es.md"`. Ninguna constante queda anclada a `scripts/`.
- **Consecuencias.** El script funciona desde cualquier cwd (test de §4 aserta esta propiedad) y un cambio de ubicación de los READMEs solo toca la constante `REPO_ROOT`.

## §3. validate_uci.py — V1–V12

### V1 — n_groups=10 sin adaptación

- **Problema.** n_groups fijo a 10 viola el contrato de `compute_oos_metrics` (n_groups ≥ 3 y n_groups × 5 ≤ N) cuando un dataset deja pocas filas de test.
- **Decisión.** n_groups adaptativo con la misma fórmula que `Session.evaluate_oot` (`backend_v3/session_state.py` líneas 1168–1172): `min(10, max(3, n_test // 5))`. Contrato citado: Hosmer–Lemeshow exige al menos tres grupos para construir los deciles y evaluar la bondad de ajuste, ya documentado en `backend_v3/session_state.py`.
- **Consecuencias.** Ningún dataset genera un n_groups ilegal y los números de Hosmer–Lemeshow del informe son comparables con los de una sesión real sobre el mismo split. El test de 30 filas de §4 aserta n_groups == 3.

### V2 — target_type implícito BINARY en car/balance/iris

- **Problema.** El target_type es BINARY implícito: car, balance e iris son K>2 y el informe trataría datos multiclase con métricas de semántica binaria.
- **Decisión.** `target_type` explícito por dataset en el manifiesto de CONFIGS: BINARY para german_credit, breast_cancer y blood_transfusion (K=2); CATEGORICAL para car, balance e iris (K>2, con target_class explícita según V9). El target_type gobierna la política de métricas (V8) y la validación del K declarado.
- **Consecuencias.** El informe declara la semántica por dataset en su tabla y las métricas multiclase se reportan por clase (V8) en lugar de inferir BINARY falso. El contrato llega a los tests (§4, ítem 12).

### V3 — Narrativa _QUALITY/_REVISION hardcoded

- **Problema.** Las secciones narrativas del informe (calidad, revisión) son texto congelado: dicen lo mismo aunque las métricas cambien.
- **Decisión.** Las plantillas `_QUALITY` y `_REVISION` pasan a moldes con placeholders alimentados por los datos reales: gini mínimo y máximo, dataset con peor métrica, conteo de datasets validados y número de suite vigente. El header y el disclaimer metodológico de sala limpia permanecen hardcoded porque su contenido no depende de métricas.
- **Consecuencias.** El informe deja de afirmar estados generales sin datos; cada placeholder tiene un valor computado y auditable en el propio informe.

### V4 — Revision notes congeladas en rc2

- **Problema.** Las notas de revisión describen el estado de la release rc2: no reflejan ningún cambio posterior de `tree_builder.py` ni de los engines.
- **Decisión.** Las revision notes se generan con stamps: la fecha de última modificación de `backend_v3/tree_builder.py` y de cada `backend_v3/*_engine.py` se obtiene con `git log -1 --format=%cd -- <archivo>` y se imprime por archivo en el informe. Cada stamp consume la guarda de árbol limpio de V5, para que el resultado sea reproducible.
- **Consecuencias.** El informe muestra la ventana real de modificación de `tree_builder.py` y de los engines, leída de git; el stamp es un recibo verificable, no una narrativa congelada.

### V5 — Sin --check ni guarda de git status

- **Problema.** La regeneración puede ejecutarse sobre un working tree sucio (engines en estado intermedio), produciendo un informe no reproducible, y no existe un modo no-mutador que diga si el informe vigente está actualizado.
- **Decisión.** Dos contratos: (a) `--check` no escribe; compara el informe vigente contra una regeneración byte-a-byte y termina exit 1 si difiere, exit 0 si idéntica (lado verificación del invariante §7-3); (b) guarda de git status: si hay cambios no commiteados en `backend_v3/`, `scripts/` o `docs/validation_results_3.6.md`, aborta con RuntimeError pidiendo árbol limpio antes de regenerar.
- **Consecuencias.** `--check` es usable en CI (§4) y la regeneración exige un árbol commiteado, porque regenerar con engines intermedios produciría un informe no reproducible.

### V6 — Degradación silenciosa a None (exit 0)

- **Problema.** Si una métrica falla al computarse, validate la deja como None en el informe y termina exit 0: el informe contiene huecos y el proceso parece exitoso.
- **Decisión.** Métrica None es error hard: cualquier métrica de la matriz que termine None (fingerprint, gini, KS, AUC y accuracy cuando aplique por V8) aborta con `RuntimeError("métrica <nombre> = None para <dataset>")` y exit 2, distinguible del exit 1 de `--check` y del exit 0 de éxito.
- **Consecuencias.** No es posible escribir un informe con huecos; la falla es detectable por exit 2 en CI y el informe que existe siempre está completo.

### V7 — CHAID solo en 2/6 datasets

- **Problema.** CHAID se ejecuta solo en 2 de los 6 datasets; los otros 4 no tienen cobertura de ese criterio y el informe no lo declara como limitación.
- **Decisión.** CHAID se ejecuta en los 6 datasets bajo la semántica del target_type de cada uno (V2): BINARY para los tres binarios y CATEGORICAL con target_class (V9) para car, balance e iris. Si un dataset resultara CHAID-incompatible (binning vacío, sin splits viables), el informe lo declara como limitación explícita por dataset, en la tabla de resultados, nunca como omisión silenciosa.
- **Consecuencias.** La cobertura de CHAID va de 2/6 a 6/6. Las comparaciones quedan intra-tipo y cada celda de la tabla CHAID declara su estado (métrica o limitación justificada).

### V8 — accuracy mezcla semántica binaria y multiclase

- **Problema.** La columna accuracy del informe junta accuracies binarias (con cutpoint) y multiclase (argmax) sin declarar la semántica: la comparación cross-dataset es inválida.
- **Decisión.** La matriz de métricas se separa por target_type: para BINARY, gini, KS, AUC y accuracy con el cutpoint del manifiesto; para CATEGORICAL, gini y accuracy de argmax, con KS por clase en sección aparte. La columna accuracy única cross-dataset desaparece del informe y cada fila nombra su semántica.
- **Consecuencias.** Las comparaciones solo se hacen intra-tipo y el informe declara la semántica de cada columna. El número de un binario nunca aparece en la misma columna que el de un multiclase.

### V9 — target_class multiclase sin justificar

- **Problema.** Para car se elige la clase mayoritaria como target_class sin documentar la razón; otra clase produciría métricas distintas y no comparables con la línea histórica.
- **Decisión.** El manifiesto por dataset declara `target_class` explícita con justificación en el docstring del CONFIG: en car se usa la clase mayoritaria por ser la clase de negocio de referencia de la validación 3.6 (baseline histórica); en balance e iris, la mayoritaria por defecto con nota. La narrativa de V3 tiene placeholder para citarla en el informe.
- **Consecuencias.** Un cambio de target_class es un cambio visible de contrato (diff del manifiesto) y queda documentado en el informe; la comparabilidad con los resultados 3.6 se preserva o se declara rota.

### V10 — pd_floor implícito en CONFIGS

- **Problema.** El suelo de PD aplicado en la validación es un número literal repetido en cada configuración, sin nombre ni cita: un cambio silencioso no es auditable.
- **Decisión.** El pd_floor pasa a una constante nombrada `PD_FLOOR` en la cabecera del script, con referencia a su origen en `docs/methodology.md`; los CONFIGS lo referencian por constante, no por literal. Si algún dataset necesitara un piso distinto, se declararía `pd_floor_override` explícito (no existe en la configuración de 3.6).
- **Consecuencias.** Un auditor encuentra el valor en un único lugar nombrado y con cita. La divergencia silenciosa cross-dataset exige ahora un cambio deliberado.

### V11 — FIXTURES relativas al cwd

- **Problema.** `FIXTURES` se resuelve relativo al cwd: la validación ejecutada desde otra carpeta no encuentra los fixtures.
- **Decisión.** FIXTURES se ancla a `__file__`: `REPO_ROOT / "tests" / "fixtures" / "uci"` con `REPO_ROOT = Path(__file__).resolve().parents[1]`. En la Fase 1 los fixtures UCI son de solo lectura (F2): validate consume, nunca escribe.
- **Consecuencias.** validate_uci.py funciona desde cualquier cwd (misma propiedad que fetch, test de §4) y garantiza que su acceso a fixtures es de solo lectura.

### V12 — sys.path anclado a scripts/

- **Problema.** La ruta insertada en `sys.path` está fijada al directorio `scripts/` para importar constantes compartidas; rota si el layout se mueve o hay symlinks.
- **Decisión.** `sys.path.insert(0, str(REPO_ROOT))` derivado de `__file__`, para importar `scripts.fetch_datasets` y las constantes compartidas. La única ruta insertada es la raíz del repo, documentada en el docstring; sin hacks `../` relativos al cwd.
- **Consecuencias.** Los imports entre scripts derivan del layout físico del repo y no del cwd; el test de path anclado verifica ambas formas de invocación (desde la raíz y desde `scripts/`).

## §4. tests/test_scripts.py

Los tests viven en un solo archivo, `tests/test_scripts.py` (la suite pasa de 561 a 561 + 6 = 567). La red está prohibida por el invariante §7-2: `urllib.request.urlopen` se monkeypatchea siempre. Los fixtures son CSV y READMEs sintéticos construidos en `tmp_path`, con cero dependencia de `data/uci/`, de los READMEs reales y de las descargas. Los tests son argless y duales (`pytest` y `python tests/test_scripts.py`, `CONVENTIONS.md` §Tests); el aislamiento usa `tempfile.TemporaryDirectory` y `unittest.mock.patch`, sin fixtures de pytest. Los exit codes se fijan por contrato: `0` = al día, `1` = pendiente/regenerable en `--check`, `2` = error de datos (métrica None en V6); los abortos en mitad de flujo usan `RuntimeError`.

Contratos as-built (6 tests, 2 por script):

- **fetch_datasets.py (2 tests).**
  - `test_fetch_parse_robust` (F3/F4): `process_row` recibe una fila ya particionada por `csv.reader`; mapea el target y lanza `ValueError` ("sin mapear") cuando el valor no está en `target_map`, nombrando dataset y valor; las filas en blanco devuelven `None`.
  - `test_fetch_idempotency_and_hash` (F1/F5/F6): `urlopen` fake devuelve un CSV en memoria con su SHA-256 real; `DATA_DIR` y `LOG_PATH` se redirigen a `tmp_path` (y `setup_logging` se neutraliza para no dejar file handles abiertos); la primera pasada de `main()` crea `<name>.csv` + sidecar `<name>.csv.sha256` y llama a `urlopen` una vez; la segunda pasada no vuelve a descargar y emite el log de skip del logger `treegov.fetch`.
- **update_readme_date.py (2 tests).**
  - `test_update_readme_check_mode` (U4/U5): READMEs sintéticos en `tmp_path`; `--check --date` con la fecha vigente igual devuelve 0 y no escribe (bytes invariados); con la fecha vigente anterior devuelve 1 y tampoco escribe.
  - `test_update_readme_atomic` (U2): con `os.replace` parcheado para fallar en el segundo rename, `run_mutate` lanza `RuntimeError` ("escritura atomica fallida"), restaura el primer target a su contenido previo, deja el segundo intacto y no deja `.tmp` huérfanos.
- **validate_uci.py (2 tests).**
  - `test_validate_n_groups_adaptive` (V1): `Session` parcheada con `test_idx` de 20 filas; `_run_one` pasa `n_groups == 4` a `evaluate_oos` (`min(10, max(3, 20 // 5))`) y la fila no queda en error.
  - `test_validate_target_type` (V2): `Session` parcheada registra los kwargs de `train`; `car_evaluation` entrena con `TargetType.CATEGORICAL` y `german_credit` con `TargetType.BINARY`.

**Reconciliación (02/11/2026).** El diseño inicial de §4 preveía 12 tests (4 por script) y el caso "30 filas de test → n_groups == 3". La fórmula V1 (`n_test // 5`) da 6 grupos con 30 filas; 3 grupos requieren 15 filas. El contrato as-built usa 20 filas → 4 grupos, que ejercita la fórmula sin depender de esa aritmética errónea. Los dos tests de `--check` de validate_uci previstos en el diseño inicial no viven aquí: se verificaron en el sanity de 1.d.1 (`_check_against_target` con informe idéntico/alterado y SHA-256 del informe invariado) para no reentrenar los 14 pares dentro de la suite.

## §5. Proceso (P1–P4)

- **P1 — los tres scripts sin tests en pytest.** Se cierra con `tests/test_scripts.py` (§4): 6 tests, duales (ejecutables con `pytest` y con `python tests/test_scripts.py`, `CONVENTIONS.md` §Tests), sin red y sin dependencia de `data/uci/`. La suite pasa de 561 a 567 al cerrar la sub-fase 1.e.1.
- **P2 — scripts/ ausente en árboles de READMEs.** El árbol de estructura de ambos READMEs incorpora la carpeta `scripts/` con una línea de descripción de los tres scripts y su rol de infraestructura de la Fase 3.6. Es un cambio cosmético: no dispara release (regla PyPI del 20/10/2026) y se agrupa en la sub-fase 1.f.1.
- **P3 — scripts/ no empaquetado en pyproject.toml.** Decisión devenida en documentación explícita: los scripts NO se empaquetan en el wheel/sdist de PyPI porque son herramientas operativas del repo (descargas de auditoría, validación de fixtures, fechas de READMEs), no parte de la superficie pública importable de TreeGov. La decisión se registra en `docs/design_decisions.md` en el cierre 1.f.1.
- **P4 — scripts/ sin guarda de escritura en data/ o archive/.** Los únicos targets de escritura legítimos de la Fase 1 son `data/uci/` (fetch) y `docs/validation_results_3.6.md` (validate). Se añade una guarda central en `scripts/` que bloquea toda escritura bajo `tests/fixtures/`, `archive/` y cualquier path no declarado como target canónico; la violación aborta con `RuntimeError` antes de abrir el file handler, con test que verifica la guarda.

## §6. Sub-fases de implementación

| Sub-fase | Alcance | Criterio de aceptación | Archivos tocados |
|----------|---------|------------------------|------------------|
| 1.b.1 | fetch_datasets.py: F1–F8 (idempotencia sidecar, destino data/uci/, csv.reader, target_map con RuntimeError, logging, reintentos, workflow de hashes, anclaje __file__) | Los 8 contratos de §1 implementados; ejecución idempotente desde la raíz y desde scripts/ | `scripts/fetch_datasets.py` |
| 1.c.1 | update_readme_date.py: U1–U6 (--check con exit 0/1, RuntimeError con patrón+ruta, temp+rename, guarda de retroceso, anclaje __file__) | Los 6 contratos de §2 implementados; modo --check verificable | `scripts/update_readme_date.py` |
| 1.d.1 | validate_uci.py: V1–V12 (n_groups adaptativo, target_type explícito, --check, guarda de git, None→exit 2, CHAID 6/6, métricas por tipo, target_class justificada, PD_FLOOR, anclajes) | Los 12 contratos de §3 implementados; informe regenerado byte-a-byte sobre árbol limpio | `scripts/validate_uci.py`, `docs/validation_results_3.6.md` |
| 1.e.1 | tests/test_scripts.py: 6 tests de §4 (2 fetch, 2 update_readme, 2 validate) | Suite de 561 a 567 PASSED; sin urlopen real; dual-mode | `tests/test_scripts.py` |
| 1.f.1 | Cierre del bloque: READMEs (P2), pyproject (P3), checklist de cierre | Checklist de 8 documentos al día; fila roadmap del backlog actualizada (F/U/V/P → ✅) | `README.md`, `README.es.md`, `pyproject.toml`, `docs/design_decisions.md`, `docs/roadmap.md`, `docs/audit_log.md` |

## §7. Invariantes

1. **Suite 561/561 entre sub-fases.** Ninguna sub-fase se commitea con la suite por debajo del conteo vigente (561 al momento de este diseño; 567 desde 1.e.1 en adelante).
2. **Sin red real en tests.** Ninguno de los 6 tests de §4 abre sockets: `urlopen` se monkeypatchea siempre. Regla fijada aquí como invariante, compatible con `CONVENTIONS.md` §Tests.
3. **Reproducibilidad byte-a-byte de `docs/validation_results_3.6.md`.** La regeneración del informe sobre un árbol limpio (guarda V5) debe producir un archivo idéntico byte a byte al vigente; `--check` es la herramienta sin escritura que lo verifica (exit 0 = idéntico).
4. **No escrituras en `data/` fuera de `fetch_datasets.py`.** Ni validate_uci ni update_readme_date ni los tests escriben bajo `data/`; la guarda de P4 lo vuelve determinista, no una expectativa social.
5. **No modificación de tests existentes salvo congelación de bug.** La Fase 1 no toca ningún test existente (ningún bug del backlog exige congelar un comportamiento falso); los 6 tests son adiciones puras en `tests/test_scripts.py`.

## §8. Referencias

- `docs/3.6_design_public_datasets.md` — diseño canónico de la Fase 3.6: selección de datasets (D1), SHA-256 determinista, `scripts/fetch_datasets.py` y fixtures versionados. Este documento corrige los defectos de implementación de esa fase (F1–F8, V1–V12).
- `docs/roadmap.md` (sección "Deferred", subsección "⏳ Backlog post-Fase 7 — Zonas grises detectadas el 02/11/2026") — inventario F/U/V/P con descripción por ID; fila viva del backlog que esta fase cierra.
- `docs/audit_log.md` (entrada del 02/11/2026, "Auditoría forense post-Fase 7 y registro del backlog de zonas grises") — origen del inventario, plan de bloques 1–3 y hallazgos de backend (T11/N1/N2) que quedan fuera de esta fase.
- `CONVENTIONS.md` (§Tests, §Caja blanca) — reglas de tests duales, conteo de suite y sala limpia. Este diseño no añade fórmulas nuevas: reutiliza la citada de `n_groups` desde `backend_v3/session_state.py::Session.evaluate_oot` y fija el principio "cero red real en tests" como invariante §7-2.
- `docs/gui_i18n_governance_design.md` — diseño gemelo de los bloques 4–5 (GUI/i18n, hallazgos T/N de GUI del backlog); hoy pendiente de creación, con separación de alcance según §0 de ambos documentos.
