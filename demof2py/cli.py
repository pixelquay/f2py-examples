"""
Command-line interface for demof2py (`f2py-workbench`).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

import uvicorn

from .auditor import audit_fortran_source, load_project_presets
from .benchmarks import (
    evaluate_matrix_and_quadrature,
    evaluate_quadratic_cancellation,
    run_performance_benchmark,
    simulate_heat_pde,
)
from .kernels import compare_all_intents
from .precision import run_ieee754_benchmark


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="f2py-workbench",
        description="Fortran-Python f2py Numerical Kernel & Diagnostic Workbench",
    )
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Launch the web workbench and REST API server")
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")

    demo_p = sub.add_parser("demo", help="Run all scalar and vector INTENT comparisons")
    demo_p.add_argument("-x", type=float, default=3.0)
    demo_p.add_argument("-y", type=float, default=2.0)

    sub.add_parser("precision", help="Run IEEE 754 precision and .f2py_f2cmap benchmark")

    bench_p = sub.add_parser("benchmark", help="Run F2PY vs NumPy vs Python performance benchmark")
    bench_p.add_argument(
        "--workload",
        choices=["dot_product", "simpson_quad", "heat_pde"],
        default="dot_product",
    )
    bench_p.add_argument("--size", type=int, default=5000)

    pde_p = sub.add_parser("pde", help="Run 1D Heat Diffusion PDE simulation (`Heat1DStep`)")
    pde_p.add_argument("--steps", type=int, default=35)
    pde_p.add_argument("--alpha", type=float, default=0.01)
    pde_p.add_argument("--pulse", choices=["gaussian", "sine", "bimodal"], default="gaussian")

    num_p = sub.add_parser("numerics", help="Run column-major MatMulDp and Simpson 1/3 quadrature explorer")
    num_p.add_argument(
        "--preset",
        choices=["rotation_scale", "spd_stiffness", "hilbert_3x3"],
        default="rotation_scale",
    )
    num_p.add_argument("--order", choices=["F", "C"], default="F")
    num_p.add_argument("--integrand", choices=["sin_pi", "exp_unit", "poly_quartic"], default="sin_pi")
    num_p.add_argument("--points", type=int, default=101)

    quad_p = sub.add_parser("quadratic", help="Run Catastrophic Cancellation vs Citardauq root stability analysis")
    quad_p.add_argument("-a", type=float, default=1.0)
    quad_p.add_argument("-b", type=float, default=1.0e8)
    quad_p.add_argument("-c", type=float, default=1.0)

    audit_p = sub.add_parser("audit", help="Audit all repository Fortran files for f2py pitfalls")
    audit_p.add_argument("--cmap", choices=["modern", "legacy"], default="modern")

    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run("demof2py.app:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.command == "precision":
        print(json.dumps(run_ieee754_benchmark(), indent=2))
        return 0

    if args.command == "benchmark":
        print(json.dumps(run_performance_benchmark(args.workload, size=args.size), indent=2))
        return 0

    if args.command == "pde":
        print(
            json.dumps(
                simulate_heat_pde(steps=args.steps, alpha=args.alpha, pulse_type=args.pulse),
                indent=2,
            )
        )
        return 0

    if args.command == "numerics":
        print(
            json.dumps(
                evaluate_matrix_and_quadrature(
                    matrix_preset=args.preset,
                    order_mode=args.order,
                    integrand=args.integrand,
                    points=args.points,
                ),
                indent=2,
            )
        )
        return 0

    if args.command == "quadratic":
        print(
            json.dumps(
                evaluate_quadratic_cancellation(a=args.a, b=args.b, c=args.c),
                indent=2,
            )
        )
        return 0

    if args.command == "audit":
        for preset in load_project_presets():
            res = audit_fortran_source(preset["code"], preset["filename"], cmap_mode=args.cmap)
            print(f"=== {res['filename']} [{res['overall_label']}] ===")
            for f in res["findings"]:
                print(f"  Line {f['line']} ({f['severity'].upper()}): {f['title']}")
        return 0

    # Default or 'demo'
    comp = compare_all_intents(x=getattr(args, "x", 3.0), y=getattr(args, "y", 2.0))
    for item in comp["results"]:
        print(f"{item['meta']['name']} ({item['meta']['intent_mode']}): {item['explanation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
