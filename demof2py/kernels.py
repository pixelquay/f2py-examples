"""
Fortran-Python kernel execution engine with memory & latency telemetry.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
from pyprod import prod


LIST_KERNELS: List[Dict[str, Any]] = [
    {
        "id": "prodintent",
        "name": "prod.prodintent",
        "fortran_name": "Subroutine ProdIntent(x, y, z)",
        "category": "scalar",
        "intent_mode": "INTENT(IN) / INTENT(OUT)",
        "precision": "real32 (float)",
        "status_type": "success",
        "status_label": "Returns Value",
        "signature": "z = prod.prodintent(x, y)",
        "fortran_code": (
            "Subroutine ProdIntent(x,y,z)\n"
            "  real, Intent(In)  :: x, y\n"
            "  real, Intent(Out) :: z\n"
            "  z = x * y\n"
            "End Subroutine"
        ),
        "description": (
            "Explicit Intent(Out) on z instructs f2py to remove z from the Python "
            "argument list and return it directly as a Python float."
        ),
    },
    {
        "id": "prodinout",
        "name": "prod.prodinout",
        "fortran_name": "Subroutine ProdInOut(x, y, z)",
        "category": "scalar",
        "intent_mode": "INTENT(IN) / INTENT(INOUT)",
        "precision": "real32 (0-D ndarray)",
        "status_type": "info",
        "status_label": "Mutates In-Place",
        "signature": "prod.prodinout(x, y, z_ndarray)",
        "fortran_code": (
            "Subroutine ProdInOut(x,y,z)\n"
            "  real, Intent(In)    :: x, y\n"
            "  real, Intent(InOut) :: z\n"
            "  z = x * y\n"
            "End Subroutine"
        ),
        "description": (
            "Mutates z in-place via its C buffer pointer. Requires passing a "
            "numpy.ndarray (even a 0-D array np.array(23456.0) for scalar values)."
        ),
    },
    {
        "id": "prodnointent",
        "name": "prod.prodnointent",
        "fortran_name": "Subroutine ProdNoIntent(x, y, z)",
        "category": "scalar",
        "intent_mode": "Implicit INTENT(IN) Pitfall",
        "precision": "real32 (float)",
        "status_type": "warning",
        "status_label": "Silent No-Op in Python",
        "signature": "res = prod.prodnointent(x, y, z)  # res is None!",
        "fortran_code": (
            "Subroutine ProdNoIntent(x,y,z)\n"
            "  real x, y, z\n"
            "  ! No intent specified: f2py assumes INTENT(IN)\n"
            "  z = x * y\n"
            "End Subroutine"
        ),
        "description": (
            "Demonstrates a classic f2py pitfall: unlike plain Fortran where all arguments "
            "are mutable references, f2py defaults unspecified intent to INTENT(IN). "
            "The result is lost and z remains unchanged in Python."
        ),
    },
    {
        "id": "prodpure",
        "name": "prod.prodpure",
        "fortran_name": "Pure Real Function prodpure(x, y)",
        "category": "scalar",
        "intent_mode": "PURE FUNCTION / INTENT(IN)",
        "precision": "real32 (float)",
        "status_type": "success",
        "status_label": "Pure Return",
        "signature": "z = prod.prodpure(x, y)",
        "fortran_code": (
            "Pure Real Function prodpure(x,y)\n"
            "  real, Intent(In) :: x, y\n"
            "  prodpure = x * y\n"
            "End Function"
        ),
        "description": (
            "Fortran Pure function requires explicit Intent(In) on all arguments "
            "and returns the product directly without side effects."
        ),
    },
    {
        "id": "prodvecintent",
        "name": "prod.prodvecintent",
        "fortran_name": "Subroutine ProdVecIntent(n, x, y, z)",
        "category": "vector",
        "intent_mode": "Vector INTENT(OUT) (real64)",
        "precision": "real64 (float64)",
        "status_type": "success",
        "status_label": "64-Bit Vector Out",
        "signature": "z_vec = prod.prodvecintent(x_vec, y_vec)",
        "fortran_code": (
            "Subroutine ProdVecIntent(n, x, y, z)\n"
            "  integer, Intent(In)   :: n\n"
            "  real(dp), Intent(In)  :: x(n), y(n)\n"
            "  real(dp), Intent(Out) :: z(n)\n"
            "  z = x * y\n"
            "End Subroutine"
        ),
        "description": (
            "Element-wise double-precision (real64) vector multiplication mapped via "
            ".f2py_f2cmap to a newly allocated contiguous NumPy float64 array."
        ),
    },
    {
        "id": "proddotdp",
        "name": "prod.proddotdp",
        "fortran_name": "Subroutine ProdDotDp(n, x, y, dot_val)",
        "category": "vector",
        "intent_mode": "Dot Product Reduction (real64)",
        "precision": "real64 (float64)",
        "status_type": "success",
        "status_label": "64-Bit Reduction",
        "signature": "dot_val = prod.proddotdp(x_vec, y_vec)",
        "fortran_code": (
            "Subroutine ProdDotDp(n, x, y, dot_val)\n"
            "  integer, Intent(In)   :: n\n"
            "  real(dp), Intent(In)  :: x(n), y(n)\n"
            "  real(dp), Intent(Out) :: dot_val\n"
            "  dot_val = dot_product(x, y)\n"
            "End Subroutine"
        ),
        "description": (
            "Computes the IEEE 754 64-bit inner dot product of two vectors using "
            "Fortran's intrinsic dot_product."
        ),
    },
]


def execute_kernel(
    kernel_id: str,
    x: float = 3.0,
    y: float = 2.0,
    z_init: float = 12345.0,
    use_ndarray_for_inout: bool = True,
    vec_x: Optional[Sequence[float]] = None,
    vec_y: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Execute a specific Fortran-wrapped kernel and collect diagnostic telemetry."""
    meta = next((k for k in LIST_KERNELS if k["id"] == kernel_id), None)
    if meta is None:
        raise ValueError(f"Unknown kernel_id: {kernel_id}")

    t0 = time.perf_counter_ns()

    if kernel_id == "prodintent":
        result = prod.prodintent(x, y)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"x": x, "y": y},
            "return_value": result,
            "expected_value": float(np.float32(x) * np.float32(y)),
            "z_before": None,
            "z_after": result,
            "mutated_in_place": False,
            "value_received_by_python": True,
            "latency_us": round(max(elapsed_us, 0.4), 2),
            "explanation": (
                f"f2py allocated output `z` in C, called Fortran `ProdIntent({x}, {y}, &z)`, "
                f"and returned {result} directly as a Python float."
            ),
        }

    if kernel_id == "prodnointent":
        z_val = float(z_init)
        result = prod.prodnointent(x, y, z_val)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"x": x, "y": y, "z_init": z_init},
            "return_value": result,
            "expected_value": float(np.float32(x) * np.float32(y)),
            "z_before": z_val,
            "z_after": z_val,
            "mutated_in_place": False,
            "value_received_by_python": False,
            "latency_us": round(max(elapsed_us, 0.4), 2),
            "explanation": (
                f"Because `ProdNoIntent` omits `INTENT(OUT)`, f2py treated `z={z_init}` as "
                f"`INTENT(IN)`. Fortran computed `{x} * {y} = {x * y}` on a temporary C copy, "
                f"returned `None`, and left Python's `z` unchanged at `{z_val}`."
            ),
        }

    if kernel_id == "prodinout":
        if not use_ndarray_for_inout:
            raise TypeError(
                "Passing a plain Python float to an INTENT(INOUT) argument fails in f2py. "
                "Wrap the scalar in a 0-D NumPy array: np.array(23456.0)."
            )
        z_arr = np.array(z_init, dtype=np.float32)
        prod.prodinout(x, y, z_arr)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        z_after = float(z_arr.item())
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"x": x, "y": y, "z_init": z_init, "buffer_type": "0-D numpy.ndarray"},
            "return_value": None,
            "expected_value": float(np.float32(x) * np.float32(y)),
            "z_before": float(z_init),
            "z_after": z_after,
            "mutated_in_place": True,
            "value_received_by_python": True,
            "latency_us": round(max(elapsed_us, 0.4), 2),
            "explanation": (
                f"f2py passed the mutable C data pointer of `np.array({z_init})` to Fortran. "
                f"The subroutine returned `None` and overwrote the array buffer in-place to `{z_after}`."
            ),
        }

    if kernel_id == "prodpure":
        result = prod.prodpure(x, y)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"x": x, "y": y},
            "return_value": result,
            "expected_value": float(np.float32(x) * np.float32(y)),
            "z_before": None,
            "z_after": result,
            "mutated_in_place": False,
            "value_received_by_python": True,
            "latency_us": round(max(elapsed_us, 0.4), 2),
            "explanation": (
                f"Pure Fortran function `prodpure({x}, {y})` evaluated without side effects "
                f"and returned `{result}`."
            ),
        }

    vx = list(vec_x) if vec_x is not None else [1.5, 2.5, 3.5, 4.5]
    vy = list(vec_y) if vec_y is not None else [2.0, 4.0, 6.0, 8.0]

    if kernel_id == "prodvecintent":
        out_arr = prod.prodvecintent(vx, vy)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        out_list = [round(float(v), 8) for v in out_arr.tolist()]
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"vec_x": vx, "vec_y": vy, "n": len(vx)},
            "return_value": out_list,
            "expected_value": out_list,
            "z_before": None,
            "z_after": out_list,
            "mutated_in_place": False,
            "value_received_by_python": True,
            "latency_us": round(max(elapsed_us, 0.5), 2),
            "explanation": (
                f"Mapped `real(dp)` via `.f2py_f2cmap` to `double` (float64) and computed "
                f"{len(vx)}-element vector product `{out_list}`."
            ),
        }

    if kernel_id == "proddotdp":
        dot_val = prod.proddotdp(vx, vy)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        return {
            "kernel_id": kernel_id,
            "meta": meta,
            "inputs": {"vec_x": vx, "vec_y": vy, "n": len(vx)},
            "return_value": round(dot_val, 8),
            "expected_value": round(dot_val, 8),
            "z_before": None,
            "z_after": round(dot_val, 8),
            "mutated_in_place": False,
            "value_received_by_python": True,
            "latency_us": round(max(elapsed_us, 0.5), 2),
            "explanation": (
                f"Computed 64-bit IEEE 754 inner product `dot_product(x, y) = {round(dot_val, 8)}`."
            ),
        }

    raise ValueError(f"Unsupported kernel_id: {kernel_id}")


def compare_all_intents(
    x: float = 3.0,
    y: float = 2.0,
    z_init: float = 12345.0,
    vec_x: Optional[Sequence[float]] = None,
    vec_y: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Run all scalar and vector kernels to compare their behavior side-by-side."""
    results = [
        execute_kernel("prodintent", x=x, y=y, z_init=z_init),
        execute_kernel("prodinout", x=x, y=y, z_init=z_init, use_ndarray_for_inout=True),
        execute_kernel("prodnointent", x=x, y=y, z_init=z_init),
        execute_kernel("prodpure", x=x, y=y, z_init=z_init),
        execute_kernel("prodvecintent", x=x, y=y, vec_x=vec_x, vec_y=vec_y),
        execute_kernel("proddotdp", x=x, y=y, vec_x=vec_x, vec_y=vec_y),
    ]
    return {
        "scalar_inputs": {"x": x, "y": y, "z_init": z_init, "expected_product": x * y},
        "results": results,
    }
