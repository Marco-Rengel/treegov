# TreeGov — Convenciones para Aider

Reglas operativas que Aider lee automáticamente en cada tarea. NO duplica
filosofía completa (ver `.treegovrules`); son recordatorios operativos.

## Sala limpia (inviolable)

- `backend_v3/` — capa analítica pura. Cero imports de Qt/PySide6.
- `frontend_v3/` — capa de presentación. Cero imports de numpy/pandas/scipy.
- Comunicación exclusiva vía `backend_v3.session_state.Session`.

Un test AST (`tests/test_gui_smoke::test_frontend_clean_room`) verifica
que no se rompa esta separación.

## Verificación obligatoria

Después de CADA tarea de edición, el humano verifica con:

    python -m pytest tests -q
    git status
    git diff --stat

Si la suite baja de 178/178 tests, no se commitea.

## Comentarios y docs

- Código: docstrings y comentarios en **inglés**.
- Docs internos (audit_log, contexto, etc.): **español**.
- Cero referencias a software privativo (SPSS, SAS, Stata, Answer Tree).

## Tests

- Duales: ejecutables con `pytest` o `python tests/test_X.py`.
- `QT_QPA_PLATFORM=offscreen` para tests GUI.
- Valores verificados a mano, no autoreferencias.

## Caja blanca

Prohibido importar: sklearn, statsmodels, xgboost, lightgbm, catboost.
Toda fórmula estadística con cita bibliográfica explícita.

## Prompts grandes

**Reglas confirmadas empíricamente (01/10/2026):**

1. **Sin código literal.** No pegar bloques de código en el prompt. Describir
   la estructura en prosa y dejar que Kimi escriba el código. Prompts con
   código literal grande fallan con 504 o devuelven basura (`!!!!!`).

2. **Un prompt = un archivo.** Cuando un cambio requiere tocar N archivos,
   hacer N sesiones separadas de Aider. Prompts multi-archivo fallan.

3. **Tamaño máximo orientativo:** si el prompt supera ~30 líneas, trocear.

4. **Si el cambio es buscar-y-reemplazar trivial (<10 líneas):** evaluar
   hacerlo manualmente en VS Code en lugar de invocar Aider. Aider rinde
   cuando hay síntesis o análisis; el reemplazo mecánico es más rápido a mano.

5. **Sin archivos innecesarios en contexto.** Al arrancar `aider archivo.py`,
   no aceptar "Add file to the chat?" salvo que el archivo aporte contexto
   esencial. Cada archivo extra suma tokens y aumenta el riesgo de 504.

## Preguntas interactivas de Aider

- `Add file to the chat? (Y)es/(N)o`: normalmente `n` — el prompt ya describe
  lo necesario. Aceptar solo si el archivo aporta información no descrita.
- `Create new file? (Y)es/(N)o`: normalmente `y` — es la confirmación para
  aplicar el cambio que crea un archivo nuevo.
- `Apply this edit?`: revisar el diff antes de responder `y`.

## Antes de editar

Si un bloque de texto largo debe insertarse en un archivo, preferir
referencias exactas ("inserta después de X") en lugar de reescribir todo
el archivo (whole edit format).

## Flujo de trabajo

Diseñar → Auditar diseño → Implementar → Testear → Documentar.
Cada cambio de código va acompañado de una entrada en `docs/audit_log.md`.