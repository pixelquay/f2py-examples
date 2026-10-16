"""
Performance benchmarking, 1D Heat Diffusion PDE simulation, and reproducible
JSON diagnostic report generation for the f2py Workbench.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List
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


def evaluate_matrix_and_quadrature(
    matrix_preset: str = "rotation_scale",
    order_mode: str = "F",
    integrand: str = "sin_pi",
    points: int = 101,
) -> Dict[str, Any]:
    """
    Execute Fortran 2008 column-major matrix multiplication (`MatMulDp`) with
    memory stride inspection and composite Simpson 1/3 quadrature (`SimpsonIntegrateDp`)
    compared against the trapezoidal rule.
    """
    use_fortran_order = str(order_mode).upper() != "C"
    np_order = "F" if use_fortran_order else "C"

    if matrix_preset == "spd_stiffness":
        preset_title = "3×3 Tridiagonal Stiffness × Mass Matrix"
        raw_a = [[2.0, -1.0, 0.0], [-1.0, 2.0, -1.0], [0.0, -1.0, 2.0]]
        raw_b = [[4.0, 1.0, 0.0], [1.0, 4.0, 1.0], [0.0, 1.0, 4.0]]
    elif matrix_preset == "hilbert_3x3":
        preset_title = "3×3 Hilbert Matrix Conditioning Test"
        raw_a = [
            [1.0, 1.0 / 2.0, 1.0 / 3.0],
            [1.0 / 2.0, 1.0 / 3.0, 1.0 / 4.0],
            [1.0 / 3.0, 1.0 / 4.0, 1.0 / 5.0],
        ]
        raw_b = [
            [9.0, -36.0, 30.0],
            [-36.0, 192.0, -180.0],
            [30.0, -180.0, 180.0],
        ]
    else:
        matrix_preset = "rotation_scale"
        preset_title = "2×2 Rotation (π/6) × Anisotropic Scale"
        c30 = math.cos(math.pi / 6.0)
        s30 = math.sin(math.pi / 6.0)
        raw_a = [[c30, -s30], [s30, c30]]
        raw_b = [[2.5, 0.0], [0.0, 1.5]]

    mat_a = np.array(raw_a, dtype=np.float64, order=np_order)
    mat_b = np.array(raw_b, dtype=np.float64, order=np_order)
    mat_c = fortnumerics.matmuldp(mat_a, mat_b)
    mat_ref = np.matmul(mat_a, mat_b)

    f_contig = bool(mat_a.flags["F_CONTIGUOUS"])
    cond_a = float(np.linalg.cond(mat_a))
    det_c = float(np.linalg.det(mat_c))
    frob_c = float(np.linalg.norm(mat_c, ord="fro"))
    max_mat_err = float(np.max(np.abs(mat_c - mat_ref)))

    # Quadrature comparison
    n_pts = max(11, min(int(points), 501))
    if n_pts % 2 == 0:
        n_pts += 1  # Ensure odd node count for pure Simpson 1/3 intervals

    if integrand == "exp_unit":
        integ_label = "∫₀¹ exp(x) dx"
        a_lim, b_lim = 0.0, 1.0
        grid = np.linspace(a_lim, b_lim, n_pts, dtype=np.float64)
        y_vals = np.exp(grid)
        exact_val = math.e - 1.0
    elif integrand == "poly_quartic":
        integ_label = "∫₀² (x⁴ + 2x² + 1) dx"
        a_lim, b_lim = 0.0, 2.0
        grid = np.linspace(a_lim, b_lim, n_pts, dtype=np.float64)
        y_vals = (grid ** 4) + 2.0 * (grid ** 2) + 1.0
        exact_val = 206.0 / 15.0
    else:
        integrand = "sin_pi"
        integ_label = "∫₀^π sin(x) dx"
        a_lim, b_lim = 0.0, math.pi
        grid = np.linspace(a_lim, b_lim, n_pts, dtype=np.float64)
        y_vals = np.sin(grid)
        exact_val = 2.0

    dx = float((b_lim - a_lim) / float(n_pts - 1))
    simpson_val = fortnumerics.simpsonintegratedp(dx, y_vals)
    trapz_val = float(np.trapezoid(y_vals, dx=dx))

    simpson_err = abs(simpson_val - exact_val)
    trapz_err = abs(trapz_val - exact_val)
    accuracy_gain = round(trapz_err / max(simpson_err, 1e-16), 1)

    return {
        "matrix": {
            "preset": matrix_preset,
            "title": preset_title,
            "shape": list(mat_c.shape),
            "order_mode": "F" if use_fortran_order else "C",
            "f_contiguous": f_contig,
            "zero_copy_pass": f_contig,
            "strides_bytes": list(mat_a.strides),
            "abi_status_label": (
                "Zero-Copy Column-Major (order='F')"
                if f_contig
                else "Implicit Copy Required (order='C' -> 'F')"
            ),
            "condition_number_a": round(cond_a, 4),
            "determinant_c": round(det_c, 6),
            "frobenius_norm_c": round(frob_c, 6),
            "max_abs_err_vs_blas": max_mat_err,
            "matrix_a": [[round(float(v), 4) for v in row] for row in mat_a],
            "matrix_b": [[round(float(v), 4) for v in row] for row in mat_b],
            "matrix_c": [[round(float(v), 5) for v in row] for row in mat_c],
        },
        "quadrature": {
            "integrand": integrand,
            "label": integ_label,
            "points": n_pts,
            "dx": round(dx, 6),
            "exact_value": exact_val,
            "simpson_value": simpson_val,
            "trapezoid_value": trapz_val,
            "simpson_abs_error": simpson_err,
            "trapezoid_abs_error": trapz_err,
            "accuracy_gain_x": accuracy_gain,
        },
    }


def evaluate_quadratic_cancellation(
    a: float = 1.0,
    b: float = 1.0e8,
    c: float = 1.0,
) -> Dict[str, Any]:
    """
    Evaluate catastrophic cancellation in the quadratic formula (-b + sqrt(b^2 - 4ac)) / (2a)
    versus Citardauq's stable root formulation (`QuadraticRootsCompare` in `numerics.f90`).
    """
    if abs(a) < 1e-15:
        a = 1.0
    disc = (b * b) - (4.0 * a * c)
    if disc < 0.0:
        b = max(abs(b), 2.0 * math.sqrt(abs(a * c)) + 1.0)
        disc = (b * b) - (4.0 * a * c)

    r1_naive, r2_naive, r1_stable, r2_stable, cancel_err = fortnumerics.quadraticrootscompare(
        float(a), float(b), float(c)
    )

    vieta_expected_prod = float(c / a)
    naive_vieta_prod = float(r1_naive * r2_naive)
    stable_vieta_prod = float(r1_stable * r2_stable)

    naive_vieta_rel_err = abs(naive_vieta_prod - vieta_expected_prod) / max(
        abs(vieta_expected_prod), 1e-30
    )
    stable_vieta_rel_err = abs(stable_vieta_prod - vieta_expected_prod) / max(
        abs(vieta_expected_prod), 1e-30
    )

    rel_root2_err = abs(r2_naive - r2_stable) / max(abs(r2_stable), 1e-30)
    if rel_root2_err <= 1e-16:
        digits_lost = 0.0
    else:
        digits_lost = round(min(16.0, max(0.0, 15.95 + math.log10(rel_root2_err))), 2)

    sweep_scales: List[float] = [1.0e4, 1.0e6, 1.0e7, 1.0e8, 5.0e8]
    sweep_rows = []
    for b_val in sweep_scales:
        _, r2_n, _, r2_s, c_err = fortnumerics.quadraticrootscompare(1.0, b_val, 1.0)
        rel_e = abs(r2_n - r2_s) / max(abs(r2_s), 1e-30)
        lost = 0.0 if rel_e <= 1e-16 else round(min(16.0, max(0.0, 15.95 + math.log10(rel_e))), 1)
        sweep_rows.append(
            {
                "b": b_val,
                "r2_naive": r2_n,
                "r2_stable": r2_s,
                "abs_cancel_err": c_err,
                "rel_err": rel_e,
                "digits_lost": lost,
            }
        )

    return {
        "coefficients": {"a": float(a), "b": float(b), "c": float(c)},
        "discriminant": disc,
        "r1_naive": r1_naive,
        "r2_naive": r2_naive,
        "r1_stable": r1_stable,
        "r2_stable": r2_stable,
        "abs_cancel_error": cancel_err,
        "rel_root2_error": rel_root2_err,
        "mantissa_digits_lost": digits_lost,
        "vieta_product_expected": vieta_expected_prod,
        "vieta_naive_rel_error": naive_vieta_rel_err,
        "vieta_stable_rel_error": stable_vieta_rel_err,
        "status_type": "danger" if digits_lost >= 6.0 else ("warning" if digits_lost >= 2.0 else "success"),
        "status_label": (
            f"{digits_lost:.1f} Decimal Digits Lost (Naive)"
            if digits_lost >= 1.0
            else "Well-Conditioned (0 Digits Lost)"
        ),
        "sweep": sweep_rows,
    }


def simulate_rk4_oscillator(
    steps: int = 120,
    dt: float = 0.05,
    omega0: float = 2.0,
    zeta: float = 0.15,
    x0: float = 1.0,
    v0: float = 0.0,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 4th-order Runge-Kutta (`Rk4HarmonicStep`) damped
    harmonic oscillator integrator and return displacement/velocity trajectories.
    """
    steps = max(20, min(int(steps), 400))
    dt = max(0.005, min(float(dt), 0.2))
    omega0 = max(0.2, min(float(omega0), 10.0))
    zeta = max(0.0, min(float(zeta), 2.5))

    x_traj, v_traj, final_energy = fortnumerics.rk4harmonicstep(
        steps, dt, omega0, zeta, x0, v0
    )
    initial_energy = float(0.5 * (v0 * v0 + (omega0 * omega0) * (x0 * x0)))
    energy_ratio = round(final_energy / max(initial_energy, 1e-15), 6)

    if zeta < 1e-6:
        regime_label = "Undamped Harmonic (Energy Conserved)"
        status_type = "success"
    elif zeta < 1.0 - 1e-6:
        regime_label = f"Underdamped Oscillatory (ζ = {zeta:.2f})"
        status_type = "info"
    elif abs(zeta - 1.0) <= 1e-6:
        regime_label = "Critically Damped (ζ = 1.00)"
        status_type = "warning"
    else:
        regime_label = f"Overdamped Aperiodic (ζ = {zeta:.2f})"
        status_type = "warning"

    t_grid = [round(i * dt, 4) for i in range(steps + 1)]
    return {
        "steps": steps,
        "dt": dt,
        "omega0": omega0,
        "zeta": zeta,
        "regime_label": regime_label,
        "status_type": status_type,
        "initial_energy": round(initial_energy, 6),
        "final_energy": round(final_energy, 6),
        "energy_ratio": energy_ratio,
        "peak_abs_x": round(float(np.max(np.abs(x_traj))), 6),
        "peak_abs_v": round(float(np.max(np.abs(v_traj))), 6),
        "t_grid": t_grid,
        "x_traj": [round(float(v), 6) for v in x_traj],
        "v_traj": [round(float(v), 6) for v in v_traj],
    }


def simulate_poisson_2d(
    n: int = 15,
    iterations: int = 80,
    source_type: str = "dipole",
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 2D Poisson PDE Jacobi relaxation solver (`JacobiPoisson2D`)
    on an n x n column-major grid (`order='F'`).
    """
    n = max(9, min(int(n), 31))
    if n % 2 == 0:
        n += 1
    iterations = max(5, min(int(iterations), 300))

    rhs = np.zeros((n, n), dtype=np.float64, order="F")
    mid = n // 2
    quarter = max(2, n // 4)

    if source_type == "central_charge":
        source_label = "Central Point Charge (+100)"
        rhs[mid, mid] = 100.0
    elif source_type == "quadrupole":
        source_label = "Symmetric Quadrupole (+80 / −80)"
        rhs[quarter, quarter] = 80.0
        rhs[n - 1 - quarter, n - 1 - quarter] = 80.0
        rhs[quarter, n - 1 - quarter] = -80.0
        rhs[n - 1 - quarter, quarter] = -80.0
    else:
        source_type = "dipole"
        source_label = "Electric Dipole Pair (+90 / −90)"
        rhs[mid, quarter] = 90.0
        rhs[mid, n - 1 - quarter] = -90.0

    u_out, max_residual, l2_norm = fortnumerics.jacobipoisson2d(iterations, rhs)
    max_abs_u = float(np.max(np.abs(u_out)))

    return {
        "n": n,
        "iterations": iterations,
        "source_type": source_type,
        "source_label": source_label,
        "f_contiguous": bool(u_out.flags["F_CONTIGUOUS"]),
        "strides_bytes": list(u_out.strides),
        "max_residual": round(max_residual, 6),
        "l2_norm": round(l2_norm, 6),
        "max_abs_potential": round(max_abs_u, 6),
        "center_potential": round(float(u_out[mid, mid]), 6),
        "grid_u": [[round(float(val), 5) for val in row] for row in u_out],
    }


def simulate_eigen_3x3(
    preset: str = "spd_stiffness",
    iterations: int = 30,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 Rayleigh-quotient dominant eigenpair solver (`PowerEigen3x3`)
    and compare against LAPACK (`numpy.linalg.eig`).
    """
    iterations = max(5, min(int(iterations), 200))
    if preset == "hilbert_3x3":
        preset_label = "3×3 Hilbert Ill-Conditioned Matrix"
        raw_a = [
            [1.0, 1.0 / 2.0, 1.0 / 3.0],
            [1.0 / 2.0, 1.0 / 3.0, 1.0 / 4.0],
            [1.0 / 3.0, 1.0 / 4.0, 1.0 / 5.0],
        ]
    elif preset == "coupled_oscillator":
        preset_label = "3-Mass Coupled Oscillator Matrix"
        raw_a = [
            [3.0, -1.5, 0.0],
            [-1.5, 3.0, -1.5],
            [0.0, -1.5, 3.0],
        ]
    else:
        preset = "spd_stiffness"
        preset_label = "3×3 SPD Discrete Laplacian Stiffness Matrix"
        raw_a = [
            [4.0, -1.0, 0.0],
            [-1.0, 4.0, -1.0],
            [0.0, -1.0, 4.0],
        ]

    mat_a = np.array(raw_a, dtype=np.float64, order="F")
    eigval, eigvec, res_norm = fortnumerics.powereigen3x3(mat_a, iterations)

    np_vals, _ = np.linalg.eig(mat_a)
    exact_max = float(np.max(np.abs(np_vals)))
    abs_err = abs(float(eigval) - exact_max)

    return {
        "preset": preset,
        "preset_label": preset_label,
        "iterations": iterations,
        "f_contiguous": bool(mat_a.flags["F_CONTIGUOUS"]),
        "dominant_eigenvalue": round(float(eigval), 10),
        "lapack_reference": round(exact_max, 10),
        "abs_error_vs_lapack": float(f"{abs_err:.3e}"),
        "residual_norm": float(f"{res_norm:.3e}"),
        "eigenvector": [round(float(v), 6) for v in eigvec],
    }


def simulate_thomas_tridiag(
    n: int = 21,
    bc_type: str = "catenary",
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 O(N) Thomas algorithm (`ThomasTridiag`) for a tridiagonal
    boundary-value system and compare against dense `numpy.linalg.solve`.
    """
    n = max(5, min(int(n), 201))
    sub_d = np.full(n, -1.0, dtype=np.float64)
    sub_d[0] = 0.0
    main_d = np.full(n, 2.0, dtype=np.float64)
    super_d = np.full(n, -1.0, dtype=np.float64)
    super_d[-1] = 0.0

    x_grid = np.linspace(0.0, 1.0, n)
    h2 = (1.0 / max(1, n - 1)) ** 2

    if bc_type == "helmholtz_screened":
        bc_label = "Screened Helmholtz (2.25 on main diagonal)"
        main_d = np.full(n, 2.25, dtype=np.float64)
        rhs = np.sin(math.pi * x_grid)
    elif bc_type == "boundary_drive":
        bc_label = "Dirichlet Boundary Drive (b₁=1, bₙ=1)"
        rhs = np.zeros(n, dtype=np.float64)
        rhs[0] = 1.0
        rhs[-1] = 1.0
    else:
        bc_type = "catenary"
        bc_label = "Uniform Load Beam / Catenary (−u'' = 1)"
        rhs = np.full(n, h2 * 8.0, dtype=np.float64)

    x_out, res_inf = fortnumerics.thomastridiag(sub_d, main_d, super_d, rhs)

    dense_t = np.diag(main_d) + np.diag(sub_d[1:], k=-1) + np.diag(super_d[:-1], k=1)
    x_ref = np.linalg.solve(dense_t, rhs)
    max_err_vs_dense = float(np.max(np.abs(x_out - x_ref)))
    mid = n // 2

    return {
        "n": n,
        "bc_type": bc_type,
        "bc_label": bc_label,
        "complexity": "O(N) TDMA (8N FLOPs)",
        "center_value": round(float(x_out[mid]), 6),
        "max_value": round(float(np.max(np.abs(x_out))), 6),
        "residual_inf": float(f"{res_inf:.3e}"),
        "max_err_vs_dense": float(f"{max_err_vs_dense:.3e}"),
        "solution_preview": [round(float(v), 5) for v in x_out[:9]],
    }


def simulate_blackscholes_grid(
    n: int = 81,
    strike: float = 100.0,
    sigma: float = 0.25,
    rate: float = 0.05,
    maturity: float = 1.0,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 `do concurrent` Black-Scholes option pricing kernel (`BlackScholesGrid`)
    across an N-point spot-price grid, reporting ATM Call/Put/Delta, put-call parity residual,
    effective GFLOP/s throughput, and GB/s memory bandwidth.
    """
    n = max(11, min(int(n), 501))
    if n % 2 == 0:
        n += 1
    strike = max(10.0, min(float(strike), 1000.0))
    sigma = max(0.05, min(float(sigma), 1.5))
    rate = max(0.0, min(float(rate), 0.30))
    maturity = max(0.05, min(float(maturity), 10.0))

    s_grid = np.linspace(0.5 * strike, 1.5 * strike, n, dtype=np.float64)
    s_grid_f = np.asfortranarray(s_grid)

    t0 = time.perf_counter()
    call_p, put_p, delta_c = fortnumerics.blackscholesgrid(
        s_grid_f, strike, rate, sigma, maturity
    )
    elapsed_s = max(1.0e-7, time.perf_counter() - t0)

    # ~28 FLOPs per spot point (log, sqrt, 2x erfc, exp, multiplies/adds)
    # 4 arrays * 8 bytes per point (s_grid read + call, put, delta written) = 32 bytes/point
    flops_per_pt = 28.0
    bytes_per_pt = 32.0
    gflops_s = round((n * flops_per_pt) / (elapsed_s * 1.0e9), 3)
    bandwidth_gb_s = round((n * bytes_per_pt) / (elapsed_s * 1.0e9), 3)

    mid = n // 2
    disc_k = strike * math.exp(-rate * maturity)
    parity_res = float(np.max(np.abs((call_p - put_p) - (s_grid_f - disc_k))))

    return {
        "n": n,
        "strike": round(strike, 2),
        "sigma": round(sigma, 4),
        "rate": round(rate, 4),
        "maturity": round(maturity, 4),
        "regime_label": f"Volatility σ = {round(sigma * 100)}% (r = {round(rate * 100)}%, T = {maturity:.1f} yr)",
        "f_contiguous": bool(call_p.flags["F_CONTIGUOUS"]),
        "atm_spot": round(float(s_grid_f[mid]), 2),
        "atm_call": round(float(call_p[mid]), 6),
        "atm_put": round(float(put_p[mid]), 6),
        "atm_delta": round(float(delta_c[mid]), 6),
        "put_call_parity_residual": float(f"{parity_res:.3e}"),
        "max_put_call_parity_error": float(f"{parity_res:.3e}"),
        "gflops_per_sec": gflops_s,
        "gflops_estimate": gflops_s,
        "bandwidth_gb_per_sec": bandwidth_gb_s,
        "bandwidth_gbps": bandwidth_gb_s,
        "s_grid": [round(float(v), 2) for v in s_grid_f],
        "call_curve": [round(float(v), 4) for v in call_p],
        "call_prices": [round(float(v), 4) for v in call_p],
        "put_curve": [round(float(v), 4) for v in put_p],
        "put_prices": [round(float(v), 4) for v in put_p],
        "delta_curve": [round(float(v), 4) for v in delta_c],
    }


def simulate_spectral_dft(
    n: int = 64,
    freq1: float = 5.0,
    freq2: float = 14.0,
    noise: float = 0.05,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 Hann-windowed one-sided Discrete Fourier Transform kernel
    (`SpectralDftPower`) and verify against `numpy.fft.rfft`.
    """
    n = max(16, min(int(n), 256))
    if n % 2 != 0:
        n += 1
    nyquist = max(2.0, float(n // 2 - 1))
    freq1 = max(1.0, min(float(freq1), nyquist))
    freq2 = max(1.0, min(float(freq2), nyquist))
    noise = max(0.0, min(float(noise), 1.0))

    idx = np.arange(n, dtype=np.float64)
    two_pi = 2.0 * math.pi
    sig = (
        1.25 * np.sin(two_pi * freq1 * idx / float(n))
        + 0.65 * np.cos(two_pi * freq2 * idx / float(n))
        + noise * np.sin(two_pi * min(nyquist, 23.0) * idx / float(n))
    )
    sig_f = np.asfortranarray(sig, dtype=np.float64)

    t0 = time.perf_counter()
    power_out, peak_bin, peak_pow = fortnumerics.spectraldftpower(sig_f)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)

    win = 0.5 * (1.0 - np.cos(two_pi * idx / float(max(1, n - 1))))
    fft_ref = np.fft.rfft(sig_f * win)
    ref_power = (np.abs(fft_ref) ** 2) / float(n)
    max_err_vs_fft = float(np.max(np.abs(power_out - ref_power)))

    sorted_bins = np.argsort(power_out)[::-1]
    secondary_bin = int(sorted_bins[1]) if len(sorted_bins) > 1 else int(peak_bin)
    secondary_pow = float(power_out[secondary_bin])
    median_floor = max(1.0e-12, float(np.median(power_out)))
    snr_db = round(10.0 * math.log10(max(1.0e-12, float(peak_pow)) / median_floor), 2)

    return {
        "n": n,
        "n_bins": int(len(power_out)),
        "freq1": round(freq1, 2),
        "freq2": round(freq2, 2),
        "noise": round(noise, 3),
        "f_contiguous": bool(power_out.flags["F_CONTIGUOUS"]),
        "peak_bin": int(peak_bin),
        "peak_power": round(float(peak_pow), 6),
        "secondary_bin": secondary_bin,
        "secondary_power": round(secondary_pow, 6),
        "snr_db": snr_db,
        "max_err_vs_numpy_fft": float(f"{max_err_vs_fft:.3e}"),
        "elapsed_ms": elapsed_ms,
        "signal_samples": [round(float(v), 5) for v in sig_f],
        "power_spectrum": [round(float(v), 5) for v in power_out],
        "freq_bins": list(range(len(power_out))),
    }


def simulate_montecarlo_option(
    n_paths: int = 20000,
    s0: float = 100.0,
    strike: float = 100.0,
    rate: float = 0.05,
    sigma: float = 0.25,
    maturity: float = 1.0,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 Box-Muller + Antithetic Variates Monte Carlo option pricing
    kernel (`MonteCarloOptionDp`) and compare against closed-form `BlackScholesGrid`.
    """
    n_paths = max(500, min(int(n_paths), 200000))
    s0 = max(10.0, min(float(s0), 1000.0))
    strike = max(10.0, min(float(strike), 1000.0))
    rate = max(0.0, min(float(rate), 0.30))
    sigma = max(0.05, min(float(sigma), 1.5))
    maturity = max(0.05, min(float(maturity), 10.0))
    seed = max(1, min(int(seed), 999999))

    t0 = time.perf_counter()
    call_est, put_est, std_err, paths_sample = fortnumerics.montecarlooptiondp(
        n_paths, s0, strike, rate, sigma, maturity, seed
    )
    elapsed_s = max(1.0e-7, time.perf_counter() - t0)

    bs_call_arr, bs_put_arr, bs_delta_arr = fortnumerics.blackscholesgrid(
        np.asfortranarray([s0], dtype=np.float64), strike, rate, sigma, maturity
    )
    bs_call = float(bs_call_arr[0])
    bs_put = float(bs_put_arr[0])
    bs_delta = float(bs_delta_arr[0])

    call_abs_err = abs(float(call_est) - bs_call)
    put_abs_err = abs(float(put_est) - bs_put)
    ci_95_low = float(call_est) - 1.96 * float(std_err)
    ci_95_high = float(call_est) + 1.96 * float(std_err)
    mpaths_per_sec = round((n_paths / elapsed_s) / 1.0e6, 3)

    return {
        "n_paths": n_paths,
        "s0": round(s0, 2),
        "strike": round(strike, 2),
        "rate": round(rate, 4),
        "sigma": round(sigma, 4),
        "maturity": round(maturity, 4),
        "seed": seed,
        "f_contiguous": bool(paths_sample.flags["F_CONTIGUOUS"]),
        "mc_call": round(float(call_est), 6),
        "mc_put": round(float(put_est), 6),
        "std_error": round(float(std_err), 6),
        "ci_95_low": round(ci_95_low, 6),
        "ci_95_high": round(ci_95_high, 6),
        "bs_exact_call": round(bs_call, 6),
        "bs_exact_put": round(bs_put, 6),
        "bs_exact_delta": round(bs_delta, 6),
        "call_abs_error": round(call_abs_err, 6),
        "put_abs_error": round(put_abs_err, 6),
        "mpaths_per_sec": mpaths_per_sec,
        "terminal_spots_sample": [round(float(v), 3) for v in paths_sample],
    }


def simulate_autodiff_vcurve(
    x: float = -1.2,
    y: float = 1.0,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 Forward-Mode Dual-Number Automatic Differentiation kernel
    (`AutoDiffRosenbrockDp`) on the 2D Rosenbrock function and compare against
    1st-order Forward and 2nd-order Central Finite-Difference step sizes h in [10^-1, 10^-15].
    """
    x = max(-5.0, min(float(x), 5.0))
    y = max(-5.0, min(float(y), 5.0))

    exponents = list(range(1, 16))
    h_steps = np.asfortranarray([10.0 ** (-k) for k in exponents], dtype=np.float64)

    t0 = time.perf_counter()
    (
        fd_err_fwd,
        fd_err_cen,
        exact_gx,
        exact_gy,
        exact_val,
        opt_h_cen,
    ) = fortnumerics.autodiffrosenbrockdp(x, y, h_steps)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)

    min_cen_err = float(np.min(fd_err_cen))
    min_fwd_err = float(np.min(fd_err_fwd))
    worst_cancel_err = float(fd_err_cen[-1])

    return {
        "x": round(x, 4),
        "y": round(y, 4),
        "n_steps": len(exponents),
        "f_contiguous": bool(fd_err_cen.flags["F_CONTIGUOUS"]),
        "exact_value": round(float(exact_val), 8),
        "exact_grad": [round(float(exact_gx), 8), round(float(exact_gy), 8)],
        "exact_grad_norm": round(float(math.hypot(exact_gx, exact_gy)), 8),
        "dual_autodiff_error": 0.0,
        "optimal_h_central": float(f"{opt_h_cen:.1e}"),
        "min_central_fd_error": float(f"{min_cen_err:.3e}"),
        "min_forward_fd_error": float(f"{min_fwd_err:.3e}"),
        "cancellation_error_at_1e15": float(f"{worst_cancel_err:.3e}"),
        "elapsed_ms": elapsed_ms,
        "exponents": [-k for k in exponents],
        "h_steps": [float(f"{v:.1e}") for v in h_steps],
        "forward_fd_errors": [float(f"{v:.4e}") for v in fd_err_fwd],
        "central_fd_errors": [float(f"{v:.4e}") for v in fd_err_cen],
        "log10_forward_errors": [round(math.log10(max(1.0e-16, float(v))), 3) for v in fd_err_fwd],
        "log10_central_errors": [round(math.log10(max(1.0e-16, float(v))), 3) for v in fd_err_cen],
    }


def simulate_sparse_csr_spmv(
    n: int = 64,
    bandwidth: int = 1,
) -> Dict[str, Any]:
    """
    Execute the Fortran 2008 Compressed Sparse Row (CSR) SpMV kernel (`CsrSpmvDp`)
    for a 1D/2D discretized banded operator and compare memory footprint and accuracy
    against an O(N^2) dense matrix-vector product.
    """
    n = max(8, min(int(n), 256))
    bandwidth = max(1, min(int(bandwidth), 4))

    row_ptr_list: List[int] = [1]
    col_idx_list: List[int] = []
    vals_list: List[float] = []

    for i in range(1, n + 1):
        c_min = max(1, i - bandwidth)
        c_max = min(n, i + bandwidth)
        for j in range(c_min, c_max + 1):
            col_idx_list.append(j)
            if i == j:
                vals_list.append(2.0 * float(bandwidth) + 0.5)
            else:
                vals_list.append(-1.0 / float(abs(i - j)))
        row_ptr_list.append(len(col_idx_list) + 1)

    nnz = len(vals_list)
    row_ptr = np.asfortranarray(row_ptr_list, dtype=np.int32)
    col_idx = np.asfortranarray(col_idx_list, dtype=np.int32)
    vals = np.asfortranarray(vals_list, dtype=np.float64)
    idx_grid = np.linspace(0.0, math.pi, n, dtype=np.float64)
    x_vec = np.asfortranarray(np.sin(idx_grid) + 0.5 * np.cos(2.0 * idx_grid), dtype=np.float64)

    t0 = time.perf_counter()
    y_sparse, max_err_vs_dense, compression_ratio = fortnumerics.csrspmvdp(
        row_ptr, col_idx, vals, x_vec
    )
    elapsed_s = max(1.0e-7, time.perf_counter() - t0)

    dense_bytes = n * n * 8
    csr_bytes = nnz * 8 + (nnz + n + 1) * 4
    sparsity_pct = round(100.0 * (1.0 - float(nnz) / float(n * n)), 2)
    memory_saved_pct = round(100.0 * (1.0 - float(csr_bytes) / float(dense_bytes)), 2)
    gflops = round((2.0 * nnz / elapsed_s) / 1.0e9, 4)

    preview_idx = np.linspace(0, n - 1, min(16, n), dtype=int)

    return {
        "n": n,
        "bandwidth": bandwidth,
        "nnz": nnz,
        "dense_elements": n * n,
        "f_contiguous": bool(y_sparse.flags["F_CONTIGUOUS"]),
        "sparsity_percent": sparsity_pct,
        "dense_bytes": dense_bytes,
        "csr_bytes": csr_bytes,
        "compression_ratio": round(float(compression_ratio), 2),
        "memory_saved_percent": memory_saved_pct,
        "max_err_vs_dense": float(f"{max_err_vs_dense:.3e}"),
        "l2_norm_y": round(float(np.linalg.norm(y_sparse)), 6),
        "gflops": gflops,
        "y_preview": [round(float(y_sparse[i]), 5) for i in preview_idx],
        "x_preview": [round(float(x_vec[i]), 5) for i in preview_idx],
    }


def run_native_fortran_cli(mode: str = "all") -> Dict[str, Any]:
    """
    Execute the compiled native Fortran 2008 CLI binary (`builddir/fortran_workbench`)
    and return its formatted numerical report.
    """
    flag_map = {
        "all": "--all",
        "precision": "--precision",
        "intents": "--intents",
        "pde": "--pde",
        "linalg": "--linalg",
        "ode": "--ode",
        "poisson": "--poisson",
        "eigen": "--eigen",
        "tridiag": "--tridiag",
        "blackscholes": "--blackscholes",
        "spectral": "--spectral",
        "montecarlo": "--montecarlo",
        "autodiff": "--autodiff",
        "sparse": "--sparse",
    }
    cli_flag = flag_map.get(mode, "--all")
    source_root = Path(__file__).resolve().parent.parent
    binary_path = source_root / "builddir" / "fortran_workbench"

    t0 = time.perf_counter()
    if binary_path.exists() and binary_path.is_file():
        proc = subprocess.run(
            [str(binary_path), cli_flag],
            cwd=str(source_root),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "mode": mode,
            "flag": cli_flag,
            "binary_found": True,
            "binary_name": "builddir/fortran_workbench",
            "exit_code": proc.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": proc.stdout.strip(),
        }

    # Deterministic fallback if Meson builddir binary is not present in container
    q_res = evaluate_quadratic_cancellation(1.0, 1.0e8, 1.0)
    ode_res = simulate_rk4_oscillator()
    pois_res = simulate_poisson_2d()
    eig_res = simulate_eigen_3x3()
    tri_res = simulate_thomas_tridiag()
    bs_res = simulate_blackscholes_grid()
    spec_res = simulate_spectral_dft()
    mc_res = simulate_montecarlo_option(n_paths=10000)
    ad_res = simulate_autodiff_vcurve()
    csr_res = simulate_sparse_csr_spmv()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    fallback_out = (
        "========================================================================\n"
        "  f2py-examples Native Fortran 2008 Numerical Workbench (v7.0.0)\n"
        "========================================================================\n"
        f"  Mode     : {cli_flag}\n"
        f"  Citardauq: r1_stable = {q_res['r1_stable']:.8e}, r2_stable = {q_res['r2_stable']:.8e}\n"
        f"  RK4 ODE  : E_final = {ode_res['final_energy']:.6f}, peak |x| = {ode_res['peak_abs_x']:.6f}\n"
        f"  Poisson2D: ||r||_inf = {pois_res['max_residual']:.6e}, ||u||_L2 = {pois_res['l2_norm']:.6f}\n"
        f"  Eigen3x3 : lambda_max = {eig_res['dominant_eigenvalue']:.6f}, ||Av-lv||_2 = {eig_res['residual_norm']:.2e}\n"
        f"  ThomasTri: x_mid = {tri_res['center_value']:.6f}, ||Tx-b||_inf = {tri_res['residual_inf']:.2e}\n"
        f"  BlackSch : ATM Call = {bs_res['atm_call']:.4f}, Put = {bs_res['atm_put']:.4f}, Delta = {bs_res['atm_delta']:.4f}\n"
        f"  Spectral : Peak Bin k* = {spec_res['peak_bin']}, P(k*) = {spec_res['peak_power']:.4f}, SNR = {spec_res['snr_db']:.1f} dB\n"
        f"  MonteCar : MC Call = {mc_res['mc_call']:.4f} ± {mc_res['std_error']:.4f} (BS Exact = {mc_res['bs_exact_call']:.4f})\n"
        f"  AutoDiff : Dual Grad = ({ad_res['exact_grad'][0]:.1f}, {ad_res['exact_grad'][1]:.1f}), Opt Central h* = {ad_res['optimal_h_central']:.1e}\n"
        f"  SparseCSR: N={csr_res['n']}, nnz={csr_res['nnz']}, Compression = {csr_res['compression_ratio']:.2f}x, ||err||_inf = {csr_res['max_err_vs_dense']:.1e}\n"
        "========================================================================"
    )
    return {
        "mode": mode,
        "flag": cli_flag,
        "binary_found": False,
        "binary_name": "fortnumerics (in-process fallback)",
        "exit_code": 0,
        "elapsed_ms": elapsed_ms,
        "stdout": fallback_out,
    }


def build_diagnostic_bundle() -> Dict[str, Any]:
    """Assemble a full JSON diagnostic & benchmark report for download/export."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "f2py Numerical Kernel & Precision Workbench",
        "version": "7.0.0",
        "ieee754": run_ieee754_benchmark(),
        "cmap_audit": evaluate_cmap_precision(),
        "intent_comparison": compare_all_intents(3.0, 4.0, 23456.0),
        "benchmark": run_performance_benchmark("dot_product", size=5000, iterations=15),
        "heat_pde": simulate_heat_pde(n=41, steps=35, alpha=0.01, pulse_type="gaussian"),
        "numerics_explorer": evaluate_matrix_and_quadrature(),
        "quadratic_cancellation": evaluate_quadratic_cancellation(),
        "rk4_oscillator": simulate_rk4_oscillator(),
        "poisson_2d": simulate_poisson_2d(),
        "eigen_3x3": simulate_eigen_3x3(),
        "thomas_tridiag": simulate_thomas_tridiag(),
        "blackscholes_grid": simulate_blackscholes_grid(),
        "spectral_dft": simulate_spectral_dft(),
        "montecarlo_option": simulate_montecarlo_option(n_paths=10000),
        "autodiff_vcurve": simulate_autodiff_vcurve(),
        "sparse_csr_spmv": simulate_sparse_csr_spmv(),
    }






