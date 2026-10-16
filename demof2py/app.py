"""
FastAPI web application & REST API for the Fortran-Python f2py Workbench.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform
import sys
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import numpy as np
from pydantic import BaseModel, Field

from . import __version__
from .auditor import (
    audit_fortran_source,
    build_jupyter_notebook,
    build_markdown_pr_report,
    build_project_zip_bundle,
    build_sarif_report,
    compile_and_execute_custom_fortran,
    generate_f2py_build_scaffold,
    load_project_presets,
    modernize_f77_to_f2008,
    verify_with_gfortran,
)
from .benchmarks import (
    build_diagnostic_bundle,
    evaluate_matrix_and_quadrature,
    evaluate_quadratic_cancellation,
    evaluate_roofline_profile,
    run_native_fortran_cli,
    run_performance_benchmark,
    simulate_autodiff_vcurve,
    simulate_blackscholes_grid,
    simulate_crank_nicolson_1d,
    simulate_eigen_3x3,
    simulate_heat_pde,
    simulate_montecarlo_option,
    simulate_newton_2d,
    simulate_poisson_2d,
    simulate_rk4_oscillator,
    simulate_sparse_csr_spmv,
    simulate_spectral_dft,
    simulate_thomas_tridiag,
)
from .kernels import LIST_KERNELS, compare_all_intents, execute_kernel
from .precision import run_ieee754_benchmark

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="f2py Fortran-Python Numerical Workbench",
    description="Interactive calculation routines, IEEE 754 precision verification, 1D Heat PDE solver, and f2py static diagnostics.",
    version=__version__,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory session run history for interactive inspection
RUN_HISTORY: List[Dict[str, Any]] = []


class KernelExecuteRequest(BaseModel):
    kernel_id: str = Field(default="prodintent", description="ID of the Fortran kernel to execute")
    x: float = Field(default=3.0, ge=-1e12, le=1e12, description="First scalar operand x")
    y: float = Field(default=2.0, ge=-1e12, le=1e12, description="Second scalar operand y")
    z_init: float = Field(
        default=12345.0,
        ge=-1e12,
        le=1e12,
        description="Initial value of z before calling ProdNoIntent or ProdInOut",
    )
    use_ndarray_for_inout: bool = Field(
        default=True,
        description="Pass 0-D numpy.ndarray buffer for INTENT(INOUT) routines",
    )
    vec_x: Optional[List[float]] = Field(
        default=None,
        description="Vector X elements for 64-bit array kernels",
    )
    vec_y: Optional[List[float]] = Field(
        default=None,
        description="Vector Y elements for 64-bit array kernels",
    )
    compare_all: bool = Field(
        default=False,
        description="If true, execute and compare all scalar and vector routines side-by-side",
    )


class AuditRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Fortran source code to audit")
    filename: str = Field(default="snippet.f90", description="Filename (.f for F77, .f90 for F90+)")
    cmap_mode: str = Field(
        default="modern",
        pattern="^(modern|legacy)$",
        description="Active .f2py_f2cmap mode: 'modern' (includes real32/real64/real128) or 'legacy' (sp/dp only)",
    )


class BenchmarkRunRequest(BaseModel):
    workload: str = Field(
        default="dot_product",
        pattern="^(dot_product|simpson_quad|heat_pde)$",
        description="Benchmark workload: dot_product, simpson_quad, or heat_pde",
    )
    size: int = Field(default=5000, ge=32, le=50000, description="Vector/grid size N")
    iterations: int = Field(default=20, ge=3, le=100, description="Iterations for timing average")


class PdeSimulateRequest(BaseModel):
    n: int = Field(default=41, ge=15, le=101, description="Spatial grid points on [0, 1]")
    steps: int = Field(default=35, ge=1, le=250, description="Number of explicit Euler time steps")
    alpha: float = Field(default=0.01, ge=0.0005, le=0.05, description="Thermal diffusivity alpha")
    pulse_type: str = Field(
        default="gaussian",
        pattern="^(gaussian|sine|bimodal)$",
        description="Initial thermal profile: gaussian, sine, or bimodal",
    )


class NumericsExploreRequest(BaseModel):
    matrix_preset: str = Field(
        default="rotation_scale",
        pattern="^(rotation_scale|spd_stiffness|hilbert_3x3)$",
        description="Matrix multiplication preset: rotation_scale, spd_stiffness, or hilbert_3x3",
    )
    order_mode: str = Field(
        default="F",
        pattern="^(F|C)$",
        description="Array memory layout order: 'F' (column-major zero-copy) or 'C' (row-major)",
    )
    integrand: str = Field(
        default="sin_pi",
        pattern="^(sin_pi|exp_unit|poly_quartic)$",
        description="Quadrature integrand: sin_pi, exp_unit, or poly_quartic",
    )
    points: int = Field(default=101, ge=11, le=501, description="Quadrature grid node count")


class QuadraticExploreRequest(BaseModel):
    a: float = Field(default=1.0, description="Quadratic coefficient a")
    b: float = Field(default=1.0e8, description="Linear coefficient b (large values trigger cancellation)")
    c: float = Field(default=1.0, description="Constant term c")


class NativeCliRunRequest(BaseModel):
    mode: str = Field(
        default="all",
        pattern="^(all|precision|intents|pde|linalg|ode|poisson|eigen|tridiag|blackscholes|spectral|montecarlo|autodiff|sparse|cranknicolson|newton)$",
        description="Native Fortran 2008 CLI flag mode: all, precision, intents, pde, linalg, ode, poisson, eigen, tridiag, blackscholes, spectral, montecarlo, autodiff, sparse, cranknicolson, or newton",
    )


class Rk4ExploreRequest(BaseModel):
    steps: int = Field(default=120, ge=20, le=400, description="Number of RK4 integration steps")
    dt: float = Field(default=0.05, ge=0.005, le=0.2, description="Time step size dt")
    omega0: float = Field(default=2.0, ge=0.2, le=10.0, description="Natural frequency omega0")
    zeta: float = Field(default=0.15, ge=0.0, le=2.5, description="Damping ratio zeta")


class Poisson2DExploreRequest(BaseModel):
    n: int = Field(default=15, ge=9, le=31, description="2D grid size n x n")
    iterations: int = Field(default=80, ge=5, le=300, description="Jacobi relaxation iterations")
    source_type: str = Field(
        default="dipole",
        pattern="^(dipole|central_charge|quadrupole)$",
        description="2D Poisson source distribution: dipole, central_charge, or quadrupole",
    )


class EigenExploreRequest(BaseModel):
    preset: str = Field(
        default="spd_stiffness",
        pattern="^(spd_stiffness|coupled_oscillator|hilbert_3x3)$",
        description="3x3 matrix preset for power iteration: spd_stiffness, coupled_oscillator, or hilbert_3x3",
    )
    iterations: int = Field(default=30, ge=5, le=200, description="Power iteration steps")


class TridiagExploreRequest(BaseModel):
    n: int = Field(default=21, ge=5, le=201, description="Tridiagonal system size N")
    bc_type: str = Field(
        default="catenary",
        pattern="^(catenary|helmholtz_screened|boundary_drive)$",
        description="Boundary-value problem type: catenary, helmholtz_screened, or boundary_drive",
    )


class BlackScholesExploreRequest(BaseModel):
    n: int = Field(default=81, ge=11, le=501, description="Spot-price grid points N")
    strike: float = Field(default=100.0, ge=10.0, le=1000.0, description="Option strike price K")
    sigma: float = Field(default=0.25, ge=0.05, le=1.5, description="Annualized volatility sigma")
    rate: float = Field(default=0.05, ge=0.0, le=0.30, description="Risk-free interest rate r")
    maturity: float = Field(default=1.0, ge=0.05, le=10.0, description="Time to maturity T (years)")


class SpectralDftExploreRequest(BaseModel):
    n: int = Field(default=64, ge=16, le=256, description="Signal sample length N")
    freq1: float = Field(default=5.0, ge=1.0, le=60.0, description="Primary harmonic bin frequency k1")
    freq2: float = Field(default=14.0, ge=1.0, le=60.0, description="Secondary harmonic bin frequency k2")
    noise: float = Field(default=0.05, ge=0.0, le=1.0, description="High-frequency harmonic noise amplitude")


class MonteCarloExploreRequest(BaseModel):
    n_paths: int = Field(default=20000, ge=500, le=200000, description="Number of Monte Carlo GBM paths")
    s0: float = Field(default=100.0, ge=10.0, le=1000.0, description="Initial spot price S0")
    strike: float = Field(default=100.0, ge=10.0, le=1000.0, description="Option strike price K")
    rate: float = Field(default=0.05, ge=0.0, le=0.30, description="Risk-free interest rate r")
    sigma: float = Field(default=0.25, ge=0.05, le=1.5, description="Annualized volatility sigma")
    maturity: float = Field(default=1.0, ge=0.05, le=10.0, description="Time to maturity T (years)")
    seed: int = Field(default=42, ge=1, le=999999, description="Deterministic LCG random seed")


class AutoDiffExploreRequest(BaseModel):
    x: float = Field(default=-1.2, ge=-5.0, le=5.0, description="Rosenbrock evaluation coordinate x")
    y: float = Field(default=1.0, ge=-5.0, le=5.0, description="Rosenbrock evaluation coordinate y")


class SparseCsrExploreRequest(BaseModel):
    n: int = Field(default=64, ge=8, le=256, description="Sparse operator dimension N x N")
    bandwidth: int = Field(default=1, ge=1, le=4, description="Half-bandwidth k (1=tridiagonal, 2=pentadiagonal)")


class CrankNicolsonExploreRequest(BaseModel):
    n: int = Field(default=41, ge=15, le=101, description="Spatial grid nodes N")
    steps: int = Field(default=30, ge=1, le=200, description="Implicit Crank-Nicolson time steps")
    alpha: float = Field(default=0.02, ge=0.001, le=0.10, description="Thermal diffusivity alpha")
    dt: float = Field(default=0.04, ge=0.001, le=0.20, description="Time step size dt")


class Newton2DExploreRequest(BaseModel):
    x0: float = Field(default=1.2, ge=-3.0, le=3.0, description="Initial guess x0")
    y0: float = Field(default=1.2, ge=-3.0, le=3.0, description="Initial guess y0")
    r_circle: float = Field(default=1.0, ge=0.25, le=2.5, description="Circle radius R in x^2 + y^2 = R^2")
    max_iters: int = Field(default=12, ge=4, le=25, description="Maximum Newton-Raphson iterations")


class RooflineExploreRequest(BaseModel):
    peak_gflops: float = Field(default=64.0, ge=8.0, le=512.0, description="Hardware peak double-precision GFLOP/s")
    peak_bw_gbps: float = Field(default=32.0, ge=4.0, le=256.0, description="Hardware peak DRAM bandwidth GB/s")


class LiveExecuteFortranRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Fortran source code to remediate, compile, and execute")
    filename: str = Field(default="snippet.f90", description="Source filename")
    x: float = Field(default=3.0, ge=-1e9, le=1e9, description="First scalar argument x")
    y: float = Field(default=4.0, ge=-1e9, le=1e9, description="Second scalar argument y")


@app.get("/api/v1/health")
def get_health() -> Dict[str, Any]:
    """Return runtime environment and Fortran/NumPy bridge health status."""
    return {
        "status": "ok",
        "version": __version__,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "platform": f"{platform.system()} {platform.machine()}",
        "cmap_configured": True,
        "mapped_kinds": ["sp", "dp", "qp", "real32", "real64", "real128"],
        "kernel_count": len(LIST_KERNELS),
    }


@app.get("/api/v1/kernels")
def get_kernels() -> Dict[str, Any]:
    """List all compiled/wrapped Fortran calculation routines."""
    return {"kernels": LIST_KERNELS}


@app.post("/api/v1/compute/prod")
def post_compute_prod(req: KernelExecuteRequest) -> Dict[str, Any]:
    """Execute a specific Fortran calculation routine or compare all INTENT modes."""
    try:
        if req.compare_all:
            comparison = compare_all_intents(
                x=req.x,
                y=req.y,
                z_init=req.z_init,
                vec_x=req.vec_x,
                vec_y=req.vec_y,
            )
            primary = execute_kernel(
                req.kernel_id,
                x=req.x,
                y=req.y,
                z_init=req.z_init,
                use_ndarray_for_inout=req.use_ndarray_for_inout,
                vec_x=req.vec_x,
                vec_y=req.vec_y,
            )
        else:
            primary = execute_kernel(
                req.kernel_id,
                x=req.x,
                y=req.y,
                z_init=req.z_init,
                use_ndarray_for_inout=req.use_ndarray_for_inout,
                vec_x=req.vec_x,
                vec_y=req.vec_y,
            )
            comparison = compare_all_intents(
                x=req.x,
                y=req.y,
                z_init=req.z_init,
                vec_x=req.vec_x,
                vec_y=req.vec_y,
            )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_entry = {
        "run_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        "kernel_id": primary["kernel_id"],
        "kernel_name": primary["meta"]["name"],
        "intent_mode": primary["meta"]["intent_mode"],
        "status_type": primary["meta"]["status_type"],
        "status_label": primary["meta"]["status_label"],
        "inputs": primary["inputs"],
        "output": primary["z_after"] if primary["return_value"] is None else primary["return_value"],
        "latency_us": primary["latency_us"],
        "value_received": primary["value_received_by_python"],
    }
    RUN_HISTORY.insert(0, run_entry)
    del RUN_HISTORY[25:]

    return {
        "primary": primary,
        "comparison": comparison,
        "run_entry": run_entry,
        "history_count": len(RUN_HISTORY),
    }


@app.get("/api/v1/history")
def get_run_history() -> Dict[str, Any]:
    """Return session calculation history."""
    return {"runs": RUN_HISTORY, "count": len(RUN_HISTORY)}


@app.delete("/api/v1/history/{run_id}")
def delete_run_history_item(run_id: str) -> Dict[str, Any]:
    """Delete a specific calculation run by ID."""
    before = len(RUN_HISTORY)
    RUN_HISTORY[:] = [r for r in RUN_HISTORY if r["run_id"] != run_id]
    if len(RUN_HISTORY) == before:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"status": "deleted", "run_id": run_id, "count": len(RUN_HISTORY)}


@app.delete("/api/v1/history")
def clear_run_history() -> Dict[str, Any]:
    """Clear all recorded session runs."""
    RUN_HISTORY.clear()
    return {"status": "cleared", "count": 0}


@app.get("/api/v1/precision/ieee754")
def get_precision_benchmark() -> Dict[str, Any]:
    """Run IEEE 754 floating-point precision and .f2py_f2cmap benchmarks."""
    return run_ieee754_benchmark()


@app.post("/api/v1/benchmarks/run")
def post_run_benchmark(req: BenchmarkRunRequest) -> Dict[str, Any]:
    """Run live head-to-head F2PY vs Vectorized NumPy vs Pure Python performance benchmark."""
    return run_performance_benchmark(
        workload=req.workload,
        size=req.size,
        iterations=req.iterations,
    )


@app.post("/api/v1/pde/simulate")
def post_simulate_pde(req: PdeSimulateRequest) -> Dict[str, Any]:
    """Execute the 1D Heat Diffusion PDE solver (`fortnumerics.heat1dstep`)."""
    return simulate_heat_pde(
        n=req.n,
        steps=req.steps,
        alpha=req.alpha,
        pulse_type=req.pulse_type,
    )


@app.post("/api/v1/numerics/explore")
def post_explore_numerics(req: NumericsExploreRequest) -> Dict[str, Any]:
    """Execute column-major MatMulDp with stride inspection and Simpson 1/3 quadrature."""
    return evaluate_matrix_and_quadrature(
        matrix_preset=req.matrix_preset,
        order_mode=req.order_mode,
        integrand=req.integrand,
        points=req.points,
    )


@app.post("/api/v1/numerics/quadratic")
def post_explore_quadratic(req: QuadraticExploreRequest) -> Dict[str, Any]:
    """Evaluate catastrophic cancellation vs Citardauq stable quadratic roots (`QuadraticRootsCompare`)."""
    return evaluate_quadratic_cancellation(
        a=req.a,
        b=req.b,
        c=req.c,
    )


@app.post("/api/v1/native-cli/run")
def post_run_native_cli(req: NativeCliRunRequest) -> Dict[str, Any]:
    """Execute the standalone native Fortran 2008 CLI binary (`builddir/fortran_workbench`)."""
    return run_native_fortran_cli(mode=req.mode)


@app.post("/api/v1/ode/rk4")
def post_explore_rk4(req: Rk4ExploreRequest) -> Dict[str, Any]:
    """Execute the 4th-order Runge-Kutta (`Rk4HarmonicStep`) damped harmonic oscillator solver."""
    return simulate_rk4_oscillator(
        steps=req.steps,
        dt=req.dt,
        omega0=req.omega0,
        zeta=req.zeta,
    )


@app.post("/api/v1/pde/poisson2d")
def post_explore_poisson2d(req: Poisson2DExploreRequest) -> Dict[str, Any]:
    """Execute the 2D Poisson PDE Jacobi relaxation solver (`JacobiPoisson2D`)."""
    return simulate_poisson_2d(
        n=req.n,
        iterations=req.iterations,
        source_type=req.source_type,
    )


@app.post("/api/v1/linalg/eigen")
def post_explore_eigen(req: EigenExploreRequest) -> Dict[str, Any]:
    """Execute the 3x3 Rayleigh-quotient dominant eigenpair solver (`PowerEigen3x3`)."""
    return simulate_eigen_3x3(
        preset=req.preset,
        iterations=req.iterations,
    )


@app.post("/api/v1/linalg/tridiag")
def post_explore_tridiag(req: TridiagExploreRequest) -> Dict[str, Any]:
    """Execute the O(N) Thomas tridiagonal linear system solver (`ThomasTridiag`)."""
    return simulate_thomas_tridiag(
        n=req.n,
        bc_type=req.bc_type,
    )


@app.post("/api/v1/quant/blackscholes")
def post_explore_blackscholes(req: BlackScholesExploreRequest) -> Dict[str, Any]:
    """Execute the vectorized Fortran 2008 `do concurrent` Black-Scholes option pricing kernel (`BlackScholesGrid`)."""
    return simulate_blackscholes_grid(
        n=req.n,
        strike=req.strike,
        sigma=req.sigma,
        rate=req.rate,
        maturity=req.maturity,
    )


@app.post("/api/v1/signal/spectral")
def post_explore_spectral(req: SpectralDftExploreRequest) -> Dict[str, Any]:
    """Execute the Hann-windowed one-sided Discrete Fourier Transform kernel (`SpectralDftPower`)."""
    return simulate_spectral_dft(
        n=req.n,
        freq1=req.freq1,
        freq2=req.freq2,
        noise=req.noise,
    )


@app.post("/api/v1/quant/montecarlo")
def post_explore_montecarlo(req: MonteCarloExploreRequest) -> Dict[str, Any]:
    """Execute the Box-Muller + Antithetic Variates Monte Carlo option pricing kernel (`MonteCarloOptionDp`)."""
    return simulate_montecarlo_option(
        n_paths=req.n_paths,
        s0=req.s0,
        strike=req.strike,
        rate=req.rate,
        sigma=req.sigma,
        maturity=req.maturity,
        seed=req.seed,
    )


@app.post("/api/v1/sciml/autodiff")
def post_explore_autodiff(req: AutoDiffExploreRequest) -> Dict[str, Any]:
    """Execute the Forward-Mode Dual-Number Auto-Diff vs Finite-Difference V-curve kernel (`AutoDiffRosenbrockDp`)."""
    return simulate_autodiff_vcurve(
        x=req.x,
        y=req.y,
    )


@app.post("/api/v1/linalg/sparse-csr")
def post_explore_sparse_csr(req: SparseCsrExploreRequest) -> Dict[str, Any]:
    """Execute the Compressed Sparse Row (CSR) SpMV kernel (`CsrSpmvDp`)."""
    return simulate_sparse_csr_spmv(
        n=req.n,
        bandwidth=req.bandwidth,
    )


@app.post("/api/v1/pde/crank-nicolson")
def post_explore_crank_nicolson(req: CrankNicolsonExploreRequest) -> Dict[str, Any]:
    """Execute the Unconditionally Stable 2nd-Order Implicit Crank-Nicolson 1D Heat PDE solver (`CrankNicolson1D`)."""
    return simulate_crank_nicolson_1d(
        n=req.n,
        steps=req.steps,
        alpha=req.alpha,
        dt=req.dt,
    )


@app.post("/api/v1/nonlinear/newton")
def post_explore_newton_2d(req: Newton2DExploreRequest) -> Dict[str, Any]:
    """Execute the 2D Coupled Nonlinear System Newton-Raphson solver (`NewtonSystem2D`)."""
    return simulate_newton_2d(
        x0=req.x0,
        y0=req.y0,
        r_circle=req.r_circle,
        max_iters=req.max_iters,
    )


@app.get("/api/v1/benchmarks/roofline")
def get_explore_roofline(peak_gflops: float = 64.0, peak_bw_gbps: float = 32.0) -> Dict[str, Any]:
    """Return the HPC Roofline Model & Arithmetic Intensity (FLOP/Byte) profile across Fortran 2008 kernels."""
    return evaluate_roofline_profile(
        peak_gflops=peak_gflops,
        peak_bw_gbps=peak_bw_gbps,
    )


@app.post("/api/v1/benchmarks/roofline")
def post_explore_roofline(req: RooflineExploreRequest) -> Dict[str, Any]:
    """Evaluate the HPC Roofline Model with custom hardware peak GFLOP/s and memory bandwidth ceilings."""
    return evaluate_roofline_profile(
        peak_gflops=req.peak_gflops,
        peak_bw_gbps=req.peak_bw_gbps,
    )


@app.post("/api/v1/auditor/execute")
@app.post("/api/v1/diagnostics/execute")
def post_execute_custom_fortran(req: LiveExecuteFortranRequest) -> Dict[str, Any]:
    """Compile and execute custom Fortran source via an ISO_C_BINDING shared library (.dylib/.so) in a sandbox."""
    return compile_and_execute_custom_fortran(
        code=req.code,
        filename=req.filename,
        x_val=req.x,
        y_val=req.y,
    )


@app.get("/api/v1/export/report")
def get_export_report() -> Dict[str, Any]:
    """Export a full JSON diagnostic & benchmark report."""
    return build_diagnostic_bundle()


@app.get("/api/v1/export/report.md")
def get_export_report_markdown() -> Response:
    """Export a publication-ready GitHub Flavored Markdown (.md) audit & benchmark report."""
    md_content = build_markdown_pr_report()
    return Response(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="f2py-audit-benchmark-report.md"',
        },
    )


@app.get("/api/v1/export/report.sarif.json")
def get_export_report_sarif() -> Dict[str, Any]:
    """Export a SARIF 2.1.0 static analysis report for GitHub Code Scanning."""
    return build_sarif_report()



@app.get("/api/v1/export/notebook.ipynb")
def get_export_notebook() -> Dict[str, Any]:
    """Export an interactive Jupyter Notebook (.ipynb) covering all Fortran-Python workbench kernels."""
    return build_jupyter_notebook()


@app.get("/api/v1/presets")
def get_presets() -> Dict[str, Any]:
    """Return all Fortran example files from the project."""
    return {"presets": load_project_presets()}


@app.post("/api/v1/diagnostics/audit")
def post_audit_fortran(req: AuditRequest) -> Dict[str, Any]:
    """Audit Fortran code for f2py compatibility and generate remediated code."""
    return audit_fortran_source(
        code=req.code,
        filename=req.filename,
        cmap_mode=req.cmap_mode,
    )


@app.post("/api/v1/diagnostics/compile-check")
def post_compile_check_fortran(req: AuditRequest) -> Dict[str, Any]:
    """Verify Fortran code syntax and warnings with GNU Fortran (-fsyntax-only -Wall -Wextra)."""
    return verify_with_gfortran(
        code=req.code,
        filename=req.filename,
    )


@app.post("/api/v1/diagnostics/scaffold")
def post_scaffold_fortran(req: AuditRequest) -> Dict[str, Any]:
    """Generate .pyf signature, PEP 561 .pyi stub, meson.build, CMakeLists.txt, and ISO_C_BINDING scaffolds."""
    return generate_f2py_build_scaffold(
        code=req.code,
        filename=req.filename,
    )


@app.post("/api/v1/diagnostics/modernize")
def post_modernize_fortran(req: AuditRequest) -> Dict[str, Any]:
    """Auto-modernize legacy Fortran 77 (.f) or untyped routines into Fortran 2008 + ISO_C_BINDING."""
    return modernize_f77_to_f2008(
        code=req.code,
        filename=req.filename,
    )


@app.post("/api/v1/diagnostics/bundle.zip")
def post_bundle_zip_fortran(req: AuditRequest) -> Response:
    """Download a ready-to-build .zip project bundle for the audited Fortran source."""
    zip_bytes = build_project_zip_bundle(
        code=req.code,
        filename=req.filename,
    )
    stem = Path(req.filename).stem.lower() or "fortmod"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}-f2py-bundle.zip"',
        },
    )



@app.get("/", response_class=HTMLResponse)
def serve_index() -> Any:
    """Serve the single-page Fortran-Python Workbench UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Workbench UI assets not found</h1>", status_code=500)
    return FileResponse(str(index_file))
