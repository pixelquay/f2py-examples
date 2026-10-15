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
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from pydantic import BaseModel, Field

from . import __version__
from .auditor import audit_fortran_source, load_project_presets
from .kernels import LIST_KERNELS, compare_all_intents, execute_kernel
from .precision import run_ieee754_benchmark

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="f2py Fortran-Python Numerical Workbench",
    description="Interactive calculation routines, IEEE 754 precision verification, and f2py static diagnostics.",
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
        description="Initial value of z before callingProdNoIntent or ProdInOut",
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


@app.get("/", response_class=HTMLResponse)
def serve_index() -> Any:
    """Serve the single-page Fortran-Python Workbench UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Workbench UI assets not found</h1>", status_code=500)
    return FileResponse(str(index_file))
