"""backend_v3 - Nucleo algoritmico de caja blanca (DecisionTree_Modeler, Fase 0).

Sala limpia: prohibido importar PySide6/PyQt aqui dentro.
Stack permitido: numpy, pandas, scipy.stats.
Prohibido: sklearn, statsmodels, xgboost, lightgbm, catboost, torch,
optbinning, scorecardpy, tensorflow, keras (bloqueado por import_guard).
"""

from .import_guard import install_import_guard

install_import_guard()
