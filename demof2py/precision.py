"""
IEEE 754 floating-point precision benchmark & .f2py_f2cmap kind mapping analyzer.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List
import numpy as np
from badprec import badprec


def _iterative_mantissa_bits_float16() -> int:
    ph = 0
    h = np.float16(1.0)
    one = np.float16(1.0)
    two = np.float16(2.0)
    while h != np.float16(h + one):
        h = np.float16(h * two)
        ph += 1
    return ph


def _iterative_mantissa_bits_float32() -> int:
    ps = 0
    s = np.float32(1.0)
    one = np.float32(1.0)
    two = np.float32(2.0)
    while s != np.float32(s + one):
        s = np.float32(s * two)
        ps += 1
    return ps


def _iterative_mantissa_bits_float64() -> int:
    pd = 0
    d = np.float64(1.0)
    one = np.float64(1.0)
    two = np.float64(2.0)
    while d != np.float64(d + one):
        d = np.float64(d * two)
        pd += 1
    return pd


def run_ieee754_benchmark() -> Dict[str, Any]:
    """
    Compute IEEE 754 mantissa bits, machine epsilon, and decimal digits across
    16-bit, 32-bit, 64-bit, and 128-bit floating-point formats, matching
    floatPrecision.f90 and floatPrecision.py.
    """
    p16 = _iterative_mantissa_bits_float16()
    p32 = _iterative_mantissa_bits_float32()
    p64 = _iterative_mantissa_bits_float64()
    # Standard IEEE 754 binary128 (quadruple precision in gfortran real128) has 113 significand bits
    p128_fortran = 113
    np_longdouble_bits = int(np.finfo(np.longdouble).nmant + 1)

    eps16 = float(2.0 ** (-(p16 - 1)))
    eps32 = float(2.0 ** (-(p32 - 1)))
    eps64 = float(2.0 ** (-(p64 - 1)))
    eps128_str = "1.92592994438723585305597794258492732e-34"

    tiers: List[Dict[str, Any]] = [
        {
            "id": "float16",
            "label": "IEEE 754 Half (16-bit)",
            "fortran_kind": "real16 (Compiler Extension)",
            "numpy_dtype": "np.float16",
            "total_bits": 16,
            "exponent_bits": 5,
            "mantissa_bits": p16,
            "decimal_digits": round(p16 * math.log10(2), 1),
            "machine_epsilon": f"{eps16:.6e}",
            "epsilon_float": eps16,
            "log10_epsilon": round(math.log10(eps16), 2),
            "pi_sample": f"{float(np.float16(math.pi)):.6f}",
            "pi_error": f"{abs(float(np.float16(math.pi)) - math.pi):.3e}",
            "supported_in_fortran": "GCC/ARM or IEEE_ARITHMETIC",
        },
        {
            "id": "float32",
            "label": "IEEE 754 Single (32-bit)",
            "fortran_kind": "real(sp) / real(real32)",
            "numpy_dtype": "np.float32",
            "total_bits": 32,
            "exponent_bits": 8,
            "mantissa_bits": p32,
            "decimal_digits": round(p32 * math.log10(2), 1),
            "machine_epsilon": f"{eps32:.8e}",
            "epsilon_float": eps32,
            "log10_epsilon": round(math.log10(eps32), 2),
            "pi_sample": f"{float(badprec.pi32):.10f}",
            "pi_error": f"{abs(float(badprec.pi32) - math.pi):.3e}",
            "supported_in_fortran": "Native (default real)",
        },
        {
            "id": "float64",
            "label": "IEEE 754 Double (64-bit)",
            "fortran_kind": "real(dp) / real(real64)",
            "numpy_dtype": "np.float64",
            "total_bits": 64,
            "exponent_bits": 11,
            "mantissa_bits": p64,
            "decimal_digits": round(p64 * math.log10(2), 1),
            "machine_epsilon": f"{eps64:.16e}",
            "epsilon_float": eps64,
            "log10_epsilon": round(math.log10(eps64), 2),
            "pi_sample": f"{float(badprec.pi64_true):.16f}",
            "pi_error": f"{abs(float(badprec.pi64_true) - math.pi):.3e}",
            "supported_in_fortran": "Native (requires .f2py_f2cmap)",
        },
        {
            "id": "float128",
            "label": "IEEE 754 Quadruple (128-bit)",
            "fortran_kind": "real(qp) / real(real128)",
            "numpy_dtype": f"np.longdouble ({np_longdouble_bits}-bit host)",
            "total_bits": 128,
            "exponent_bits": 15,
            "mantissa_bits": p128_fortran,
            "decimal_digits": round(p128_fortran * math.log10(2), 1),
            "machine_epsilon": eps128_str,
            "epsilon_float": 1.9259299443872359e-34,
            "log10_epsilon": -33.72,
            "pi_sample": "3.1415926535897932384626433832795028",
            "pi_error": "1.926e-34",
            "supported_in_fortran": "Native in gfortran (libquadmath)",
        },
    ]

    cmap_comparison = evaluate_cmap_precision()

    return {
        "tiers": tiers,
        "cmap_comparison": cmap_comparison,
    }


def evaluate_cmap_precision() -> Dict[str, Any]:
    """Compare badprec.f90 constants with and without .f2py_f2cmap kind mappings."""
    ref_pi = "3.14159265358979323846"
    pi32_val = float(badprec.pi32)
    pi64_lit_bug = float(badprec.pi64)
    pi64_true_val = float(badprec.pi64_true)

    cases = [
        {
            "id": "unmapped_real64",
            "title": "Missing `real64` in `.f2py_f2cmap` (Legacy Bug)",
            "fortran_decl": "real(real64), parameter :: pi64 = 4.0_real64 * atan(1.0_real64)",
            "cmap_entry": "dict(real=dict(sp='float', dp='double'))  # real64 missing!",
            "resolved_c_type": "float (32-bit truncation)",
            "value_str": f"{pi32_val:.16f}",
            "abs_error": f"{abs(pi32_val - math.pi):.3e}",
            "accurate_digits": 7,
            "status": "danger",
            "status_label": "Truncated to 32-Bit",
        },
        {
            "id": "single_prec_literal",
            "title": "Single-Precision Literal in `real64` (`badprec.f90` Line 10)",
            "fortran_decl": "real(real64), parameter :: pi64 = 4*atan(1.)",
            "cmap_entry": "dict(real=dict(real64='double'))",
            "resolved_c_type": "double (64-bit storage, 32-bit RHS evaluation)",
            "value_str": f"{pi64_lit_bug:.16f}",
            "abs_error": f"{abs(pi64_lit_bug - math.pi):.3e}",
            "accurate_digits": 7,
            "status": "warning",
            "status_label": "Literal Promotion Loss",
        },
        {
            "id": "mapped_true_real64",
            "title": "Mapped `real64` + `_real64` Kind Literal (Production Fix)",
            "fortran_decl": "real(real64), parameter :: pi64_true = 4.0_real64 * atan(1.0_real64)",
            "cmap_entry": "dict(real=dict(sp='float', dp='double', real32='float', real64='double'))",
            "resolved_c_type": "double (Full 64-bit IEEE 754)",
            "value_str": f"{pi64_true_val:.16f}",
            "abs_error": f"{abs(pi64_true_val - math.pi):.3e}",
            "accurate_digits": 16,
            "status": "success",
            "status_label": "Full 53-Bit Precision",
        },
    ]

    return {
        "reference_pi": ref_pi,
        "cases": cases,
    }
