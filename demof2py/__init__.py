"""
demof2py: Production Fortran-Python f2py Numerical Kernel & Diagnostic Workbench.
"""
from .kernels import execute_kernel, compare_all_intents, LIST_KERNELS
from .precision import run_ieee754_benchmark, evaluate_cmap_precision
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
    run_performance_benchmark,
    simulate_heat_pde,
    evaluate_matrix_and_quadrature,
    evaluate_quadratic_cancellation,
    simulate_rk4_oscillator,
    simulate_poisson_2d,
    simulate_eigen_3x3,
    simulate_thomas_tridiag,
    simulate_blackscholes_grid,
    simulate_spectral_dft,
    simulate_montecarlo_option,
    simulate_autodiff_vcurve,
    simulate_sparse_csr_spmv,
    run_native_fortran_cli,
    build_diagnostic_bundle,
)

__version__ = "8.0.0"

__all__ = [
    "__version__",
    "execute_kernel",
    "compare_all_intents",
    "LIST_KERNELS",
    "run_ieee754_benchmark",
    "evaluate_cmap_precision",
    "audit_fortran_source",
    "build_jupyter_notebook",
    "build_markdown_pr_report",
    "build_project_zip_bundle",
    "build_sarif_report",
    "compile_and_execute_custom_fortran",
    "generate_f2py_build_scaffold",
    "load_project_presets",
    "modernize_f77_to_f2008",
    "verify_with_gfortran",
    "run_performance_benchmark",
    "simulate_heat_pde",
    "evaluate_matrix_and_quadrature",
    "evaluate_quadratic_cancellation",
    "simulate_rk4_oscillator",
    "simulate_poisson_2d",
    "simulate_eigen_3x3",
    "simulate_thomas_tridiag",
    "simulate_blackscholes_grid",
    "simulate_spectral_dft",
    "simulate_montecarlo_option",
    "simulate_autodiff_vcurve",
    "simulate_sparse_csr_spmv",
    "run_native_fortran_cli",
    "build_diagnostic_bundle",
]




