"""
demof2py: Production Fortran-Python f2py Numerical Kernel & Diagnostic Workbench.
"""
from .kernels import execute_kernel, compare_all_intents, LIST_KERNELS
from .precision import run_ieee754_benchmark, evaluate_cmap_precision
from .auditor import audit_fortran_source, load_project_presets

__version__ = "2.0.0"

__all__ = [
    "__version__",
    "execute_kernel",
    "compare_all_intents",
    "LIST_KERNELS",
    "run_ieee754_benchmark",
    "evaluate_cmap_precision",
    "audit_fortran_source",
    "load_project_presets",
]
