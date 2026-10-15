import numpy as np

class _BadPrecModule:
    pi32: np.float32
    pi64: np.float64
    pi64_unmapped: np.float32
    pi64_true: np.float64

badprec: _BadPrecModule
