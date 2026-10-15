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

    audit_p = sub.add_parser("audit", help="Audit all repository Fortran files for f2py pitfalls")
    audit_p.add_argument("--cmap", choices=["modern", "legacy"], default="modern")

    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run("demof2py.app:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.command == "precision":
        print(json.dumps(run_ieee754_benchmark(), indent=2))
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
