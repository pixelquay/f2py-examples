"""
badprec: Demonstrates f2py kind mapping (.f2py_f2cmap) and Fortran literal promotion.

Contrasts:
1. `pi32`: Single-precision 32-bit float `4.0_real32 * atan(1.0_real32)`
2. `pi64_unmapped`: 64-bit parameter truncated to 32-bit float when `real64` is missing from `.f2py_f2cmap`
3. `pi64`: `real(real64) :: pi64 = 4*atan(1.)` (single-precision literal widened to 64-bit)
4. `pi64_true`: True 64-bit IEEE 754 `4.0_real64 * atan(1.0_real64)` with `real64` mapped in `.f2py_f2cmap`
"""
from __future__ import annotations

import numpy as np


class _BadPrecModule:
    """Fortran module `badprec` precision constants."""

    # 32-bit IEEE 754 evaluation: 4.0_real32 * atan(1.0_real32)
    pi32: np.float32 = np.float32(4.0) * np.arctan(np.float32(1.0))

    # 64-bit parameter initialized from default single-precision literal `4*atan(1.)`
    pi64: np.float64 = np.float64(np.float32(4.0) * np.arctan(np.float32(1.0)))

    # Unmapped kind behavior when real64 is omitted from .f2py_f2cmap
    pi64_unmapped: np.float32 = np.float32(4.0) * np.arctan(np.float32(1.0))

    # True 64-bit IEEE 754 evaluation: 4.0_real64 * atan(1.0_real64)
    pi64_true: np.float64 = np.float64(4.0) * np.arctan(np.float64(1.0))


badprec = _BadPrecModule()

__all__ = ["badprec"]
