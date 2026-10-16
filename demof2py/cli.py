"""
Command-line interface for demof2py (`f2py-workbench`).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

import uvicorn

from .auditor import (
    audit_fortran_source,
    build_markdown_pr_report,
    generate_f2py_build_scaffold,
    load_project_presets,
    modernize_f77_to_f2008,
    verify_with_gfortran,
)
from .benchmarks import (
    evaluate_matrix_and_quadrature,
    evaluate_quadratic_cancellation,
    run_performance_benchmark,
    simulate_blackscholes_grid,
    simulate_eigen_3x3,
    simulate_heat_pde,
    simulate_montecarlo_option,
    simulate_poisson_2d,
    simulate_rk4_oscillator,
    simulate_spectral_dft,
    simulate_thomas_tridiag,
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

    ode_p = sub.add_parser("ode", help="Run 4th-order Runge-Kutta (`Rk4HarmonicStep`) oscillator simulation")
    ode_p.add_argument("--steps", type=int, default=120)
    ode_p.add_argument("--dt", type=float, default=0.05)
    ode_p.add_argument("--omega0", type=float, default=2.0)
    ode_p.add_argument("--zeta", type=float, default=0.15)

    pois_p = sub.add_parser("poisson", help="Run 2D Poisson PDE Jacobi relaxation (`JacobiPoisson2D`)")
    pois_p.add_argument("-n", type=int, default=15)
    pois_p.add_argument("--iterations", type=int, default=80)
    pois_p.add_argument("--source", choices=["dipole", "central_charge", "quadrupole"], default="dipole")

    eig_p = sub.add_parser("eigen", help="Run 3x3 Rayleigh-quotient dominant eigenpair (`PowerEigen3x3`)")
    eig_p.add_argument(
        "--preset",
        choices=["spd_stiffness", "coupled_oscillator", "hilbert_3x3"],
        default="spd_stiffness",
    )
    eig_p.add_argument("--iterations", type=int, default=30)

    tri_p = sub.add_parser("tridiag", help="Run O(N) Thomas tridiagonal linear solver (`ThomasTridiag`)")
    tri_p.add_argument("-n", type=int, default=21)
    tri_p.add_argument(
        "--bc",
        choices=["catenary", "helmholtz_screened", "boundary_drive"],
        default="catenary",
    )

    bs_p = sub.add_parser("blackscholes", help="Run vectorized do concurrent Black-Scholes grid (`BlackScholesGrid`)")
    bs_p.add_argument("-n", type=int, default=81)
    bs_p.add_argument("--strike", type=float, default=100.0)
    bs_p.add_argument("--sigma", type=float, default=0.25)
    bs_p.add_argument("--rate", type=float, default=0.05)
    bs_p.add_argument("--maturity", type=float, default=1.0)

    spec_p = sub.add_parser("spectral", help="Run Hann-windowed Spectral DFT Power Spectrum (`SpectralDftPower`)")
    spec_p.add_argument("-n", type=int, default=64)
    spec_p.add_argument("--freq1", type=float, default=5.0)
    spec_p.add_argument("--freq2", type=float, default=14.0)
    spec_p.add_argument("--noise", type=float, default=0.05)

    mc_p = sub.add_parser("montecarlo", help="Run Box-Muller Antithetic Monte Carlo Option Pricer (`MonteCarloOptionDp`)")
    mc_p.add_argument("--paths", type=int, default=20000)
    mc_p.add_argument("--s0", type=float, default=100.0)
    mc_p.add_argument("--strike", type=float, default=100.0)
    mc_p.add_argument("--rate", type=float, default=0.05)
    mc_p.add_argument("--sigma", type=float, default=0.25)
    mc_p.add_argument("--maturity", type=float, default=1.0)
    mc_p.add_argument("--seed", type=int, default=42)

    sub.add_parser("report-md", help="Generate publication-ready GitHub Flavored Markdown audit & benchmark report")

    audit_p = sub.add_parser("audit", help="Audit all repository Fortran files for f2py pitfalls")
    audit_p.add_argument("--cmap", choices=["modern", "legacy"], default="modern")
    audit_p.add_argument("--compile-check", action="store_true", help="Run gfortran -fsyntax-only verification")

    scaf_p = sub.add_parser("scaffold", help="Generate .pyf signature, .pyi stub, meson.build, and CMakeLists.txt")
    scaf_p.add_argument("--preset", default="numerics_f90", help="Preset ID to scaffold (default: numerics_f90)")

    mod_p = sub.add_parser("modernize", help="Auto-modernize Fortran 77 (.f) to Fortran 2008 (.f90) + ISO_C_BINDING")
    mod_p.add_argument("--preset", default="badcomment_f", help="Preset ID to modernize (default: badcomment_f)")

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

    if args.command == "ode":
        print(
            json.dumps(
                simulate_rk4_oscillator(
                    steps=args.steps, dt=args.dt, omega0=args.omega0, zeta=args.zeta
                ),
                indent=2,
            )
        )
        return 0

    if args.command == "poisson":
        print(
            json.dumps(
                simulate_poisson_2d(n=args.n, iterations=args.iterations, source_type=args.source),
                indent=2,
            )
        )
        return 0

    if args.command == "eigen":
        print(
            json.dumps(
                simulate_eigen_3x3(preset=args.preset, iterations=args.iterations),
                indent=2,
            )
        )
        return 0

    if args.command == "tridiag":
        print(
            json.dumps(
                simulate_thomas_tridiag(n=args.n, bc_type=args.bc),
                indent=2,
            )
        )
        return 0

    if args.command == "blackscholes":
        print(
            json.dumps(
                simulate_blackscholes_grid(
                    n=args.n,
                    strike=args.strike,
                    sigma=args.sigma,
                    rate=args.rate,
                    maturity=args.maturity,
                ),
                indent=2,
            )
        )
        return 0

    if args.command == "spectral":
        print(
            json.dumps(
                simulate_spectral_dft(
                    n=args.n,
                    freq1=args.freq1,
                    freq2=args.freq2,
                    noise=args.noise,
                ),
                indent=2,
            )
        )
        return 0

    if args.command == "montecarlo":
        print(
            json.dumps(
                simulate_montecarlo_option(
                    n_paths=args.paths,
                    s0=args.s0,
                    strike=args.strike,
                    rate=args.rate,
                    sigma=args.sigma,
                    maturity=args.maturity,
                    seed=args.seed,
                ),
                indent=2,
            )
        )
        return 0

    if args.command == "report-md":
        print(build_markdown_pr_report())
        return 0

    if args.command == "scaffold":
        presets = load_project_presets()
        chosen = next((p for p in presets if p["id"] == args.preset), presets[0])
        print(
            json.dumps(
                generate_f2py_build_scaffold(chosen["code"], chosen["filename"]),
                indent=2,
            )
        )
        return 0

    if args.command == "modernize":
        presets = load_project_presets()
        chosen = next((p for p in presets if p["id"] == args.preset), presets[0])
        print(
            json.dumps(
                modernize_f77_to_f2008(chosen["code"], chosen["filename"]),
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
            if args.compile_check:
                c_res = verify_with_gfortran(preset["code"], preset["filename"])
                print(f"  [{c_res['status_label']}] {c_res['command']}")
        return 0

    # Default or 'demo'
    comp = compare_all_intents(x=getattr(args, "x", 3.0), y=getattr(args, "y", 2.0))
    for item in comp["results"]:
        print(f"{item['meta']['name']} ({item['meta']['intent_mode']}): {item['explanation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

