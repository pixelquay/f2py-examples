"""
Performance benchmarking, 1D Heat Diffusion PDE simulation, and reproducible
JSON diagnostic report generation for the f2py Workbench.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import time
from typing import Any, Dict
import numpy as np

from fortnumerics import fortnumerics
from pyprod import prod
from .kernels import compare_all_intents
from .precision import evaluate_cmap_precision, run_ieee754_benchmark


def run_performance_benchmark(
    workload: str = "dot_product",
    size: int = 5000,
    iterations: int = 20,
) -> Dict[str, Any]:
    """
    Compare execution latency (microseconds) and numerical agreement across:
    1. F2PY Fortran Bridge (`pyprod` / `fortnumerics` column-major C-buffer)
    2. Vectorized NumPy array operations
    3. Pure Python loop execution
    """
    n = max(32, min(int(size), 50000))
    iters = max(3, min(int(iterations), 100))

    rng = np.random.default_rng(42)
    x = np.asfortranarray(rng.uniform(0.5, 2.5, size=n), dtype=np.float64)
    y = np.asfortranarray(rng.uniform(0.5, 2.5, size=n), dtype=np.float64)
    x_list = x.tolist()
    y_list = y.tolist()

    if workload == "simpson_quad":
        title = "Composite Simpson 1/3 Quadrature (real64)"
        fortran_routine = "fortnumerics.simpsonintegratedp(dx, y)"
        dx = math.pi / float(n - 1)
        grid = np.linspace(0.0, math.pi, n, dtype=np.float64)
        y_sin = np.sin(grid)
        y_sin_list = y_sin.tolist()

        t0 = time.perf_counter()
        f2py_val = 0.0
        for _ in range(iters):
            f2py_val = fortnumerics.simpsonintegratedp(dx, y_sin)
        f2py_us = ((time.perf_counter() - t0) / iters) * 1e6

        t0 = time.perf_counter()
        np_val = 0.0
        for _ in range(iters):
            np_val = float(np.trapezoid(y_sin, dx=dx))
        numpy_us = ((time.perf_counter() - t0) / iters) * 1e6

        py_iters = max(2, min(iters, 8))
        t0 = time.perf_counter()
        py_val = 0.0
        for _ in range(py_iters):
            acc = y_sin_list[0] + y_sin_list[-1]
            for i in range(1, n - 1):
                acc += (4.0 if i % 2 == 1 else 2.0) * y_sin_list[i]
            py_val = (dx / 3.0) * acc
        python_us = ((time.perf_counter() - t0) / py_iters) * 1e6

        max_abs_diff = abs(f2py_val - 2.0)
        result_summary = f"∫₀^π sin(x)dx = {f2py_val:.12f} (exact = 2.0, |err| = {max_abs_diff:.2e})"

    elif workload == "heat_pde":
        title = "1D Heat Diffusion Stencil (20 steps, real64)"
        fortran_routine = "fortnumerics.heat1dstep(steps, alpha, dx, dt, u0)"
        n_pde = max(31, min(n, 2001))
        dx = 1.0 / float(n_pde - 1)
        alpha = 0.01
        dt = 0.25 * (dx * dx) / alpha
        u0 = np.sin(np.linspace(0.0, math.pi, n_pde, dtype=np.float64))
        u0_list = u0.tolist()

        t0 = time.perf_counter()
        u_f2py = u0
        for _ in range(iters):
            u_f2py, _, _ = fortnumerics.heat1dstep(10, alpha, dx, dt, u0)
        f2py_us = ((time.perf_counter() - t0) / iters) * 1e6

        r_cfl = alpha * dt / (dx * dx)
        t0 = time.perf_counter()
        u_np = u0.copy()
        for _ in range(iters):
            u_np = u0.copy()
            for _ in range(10):
                u_np[1:-1] = u_np[1:-1] + r_cfl * (u_np[:-2] - 2.0 * u_np[1:-1] + u_np[2:])
        numpy_us = ((time.perf_counter() - t0) / iters) * 1e6

        py_iters = max(2, min(iters, 6))
        t0 = time.perf_counter()
        u_py = list(u0_list)
        for _ in range(py_iters):
            curr = list(u0_list)
            nxt = list(u0_list)
            for _ in range(10):
                for i in range(1, n_pde - 1):
                    nxt[i] = curr[i] + r_cfl * (curr[i - 1] - 2.0 * curr[i] + curr[i + 1])
                curr = list(nxt)
            u_py = curr
        python_us = ((time.perf_counter() - t0) / py_iters) * 1e6

        max_abs_diff = float(np.max(np.abs(u_f2py - np.asarray(u_py))))
        result_summary = f"Center peak u(0.5) = {float(u_f2py[n_pde // 2]):.6f}, max |F90 - Py| = {max_abs_diff:.2e}"
        n = n_pde

    else:
        workload = "dot_product"
        title = "Double-Precision Dot Product (ProdDotDp, real64)"
        fortran_routine = "pyprod.prod.proddotdp(x, y, n)"

        t0 = time.perf_counter()
        f2py_val = 0.0
        for _ in range(iters):
            f2py_val = prod.proddotdp(x, y, n)
        f2py_us = ((time.perf_counter() - t0) / iters) * 1e6

        t0 = time.perf_counter()
        np_val = 0.0
        for _ in range(iters):
            np_val = float(np.dot(x, y))
        numpy_us = ((time.perf_counter() - t0) / iters) * 1e6

        py_iters = max(2, min(iters, 10))
        t0 = time.perf_counter()
        py_val = 0.0
        for _ in range(py_iters):
            acc = 0.0
            for xi, yi in zip(x_list, y_list):
                acc += xi * yi
            py_val = acc
        python_us = ((time.perf_counter() - t0) / py_iters) * 1e6

        max_abs_diff = abs(f2py_val - py_val)
        result_summary = f"dot(x, y) = {f2py_val:.6f} (max |F90 - Py| = {max_abs_diff:.2e})"

    speedup_vs_python = round(python_us / max(f2py_us, 0.05), 1)
    series = [
        {
            "id": "f2py_bridge",
            "label": "F2PY Contiguous Bridge",
            "latency_us": round(f2py_us, 2),
            "relative_speedup": f"{speedup_vs_python}x faster",
            "tone": "accent",
        },
        {
            "id": "numpy_vectorized",
            "label": "Vectorized NumPy C-API",
            "latency_us": round(numpy_us, 2),
            "relative_speedup": f"{round(python_us / max(numpy_us, 0.05), 1)}x faster",
            "tone": "success",
        },
        {
            "id": "python_loop",
            "label": "Pure Python Loop (Baseline)",
            "latency_us": round(python_us, 2),
            "relative_speedup": "1.0x baseline",
            "tone": "warning",
        },
    ]

    return {
        "workload": workload,
        "title": title,
        "fortran_routine": fortran_routine,
        "size": n,
        "iterations": iters,
        "f2py_us": round(f2py_us, 2),
        "numpy_us": round(numpy_us, 2),
        "python_us": round(python_us, 2),
        "speedup_vs_python": speedup_vs_python,
        "max_abs_diff": max_abs_diff,
        "result_summary": result_summary,
        "series": series,
    }


def simulate_heat_pde(
    n: int = 41,
    steps: int = 35,
    alpha: float = 0.01,
    pulse_type: str = "gaussian",
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 1D Heat Diffusion stencil (`Heat1DStep`) and
    Citardauq quadratic root stability check (`QuadraticRootsCompare`).
    """
    grid_n = max(15, min(int(n), 101))
    num_steps = max(1, min(int(steps), 250))
    alpha_val = max(0.0005, min(float(alpha), 0.05))

    dx = 1.0 / float(grid_n - 1)
    # Choose dt so default alpha=0.01 produces stable CFL ~ 0.32, while high alpha approaches 0.5 limit
    dt = 0.0005 * (40.0 / float(grid_n - 1)) ** 2
    x_grid = np.linspace(0.0, 1.0, grid_n, dtype=np.float64)

    if pulse_type == "sine":
        u_init = np.sin(math.pi * x_grid)
        pulse_label = "Fundamental Sine Mode sin(πx)"
    elif pulse_type == "bimodal":
        u_init = np.exp(-((x_grid - 0.3) ** 2) / 0.008) + 0.85 * np.exp(-((x_grid - 0.72) ** 2) / 0.008)
        u_init[0] = 0.0
        u_init[-1] = 0.0
        pulse_label = "Dual Thermal Pulse (Bimodal)"
    else:
        pulse_type = "gaussian"
        u_init = np.exp(-((x_grid - 0.5) ** 2) / 0.015)
        u_init[0] = 0.0
        u_init[-1] = 0.0
        pulse_label = "Centered Gaussian Thermal Pulse"

    init_l2 = float(np.sqrt(np.sum(u_init * u_init) * dx))
    u_final, cfl_number, final_l2 = fortnumerics.heat1dstep(
        num_steps, alpha_val, dx, dt, u_init
    )

    is_stable = cfl_number <= 0.500001
    peak_init = float(np.max(u_init))
    peak_final = float(np.max(u_final))
    peak_retention_pct = round((peak_final / max(peak_init, 1e-12)) * 100.0, 1)

    r1_n, r2_n, r1_s, r2_s, cancel_err = fortnumerics.quadraticrootscompare(1.0, 1.0e8, 1.0)

    return {
        "n": grid_n,
        "steps": num_steps,
        "alpha": alpha_val,
        "dx": round(dx, 5),
        "dt": round(dt, 6),
        "pulse_type": pulse_type,
        "pulse_label": pulse_label,
        "cfl_number": round(cfl_number, 4),
        "cfl_limit": 0.5,
        "is_stable": is_stable,
        "stability_label": "CFL Stable (r ≤ 0.5)" if is_stable else "CFL Unstable (r > 0.5)",
        "init_l2_energy": round(init_l2, 6),
        "final_l2_energy": round(final_l2, 6),
        "peak_init": round(peak_init, 4),
        "peak_final": round(peak_final, 4),
        "peak_retention_pct": peak_retention_pct,
        "x_grid": [round(float(v), 4) for v in x_grid],
        "u_init": [round(float(v), 5) for v in u_init],
        "u_final": [round(float(v), 5) for v in u_final],
        "quadratic_stability": {
            "equation": "x² + 10⁸ x + 1 = 0",
            "naive_small_root": r2_n,
            "citardauq_stable_root": r2_s,
            "cancellation_error": cancel_err,
        },
    }


def build_diagnostic_bundle() -> Dict[str, Any]:
    """Assemble a full JSON diagnostic & benchmark report for download/export."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "f2py Numerical Kernel & Precision Workbench",
        "version": "2.1.0",
        "ieee754": run_ieee754_benchmark(),
        "cmap_audit": evaluate_cmap_precision(),
        "intent_comparison": compare_all_intents(3.0, 4.0, 23456.0),
        "benchmark": run_performance_benchmark("dot_product", size=5000, iterations=15),
        "heat_pde": simulate_heat_pde(n=41, steps=35, alpha=0.01, pulse_type="gaussian"),
    }
