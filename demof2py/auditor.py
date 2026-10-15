"""
Static Fortran & .f2py_f2cmap readiness auditor for f2py integration.

Detects:
1. Inline `!` comments in fixed-form Fortran 77 (`.f` / `.for`) files.
2. Missing `implicit none` in modules, programs, or top-level subroutines.
3. Subroutine arguments missing explicit `INTENT(IN|OUT|INOUT)`.
4. Unmapped `real(kind)` specifiers not present in `.f2py_f2cmap`.
5. Single-precision floating-point literals assigned to 64-bit/128-bit targets.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional

SOURCE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CMAP_KINDS = {"sp", "dp", "qp", "real32", "real64", "real128"}
LEGACY_CMAP_KINDS = {"sp", "dp"}


def load_project_presets() -> List[Dict[str, Any]]:
    """Load the repository's real Fortran example files as interactive presets."""
    preset_specs = [
        {
            "id": "badcomment_f77",
            "filename": "badcomment.f",
            "title": "Fortran 77 Disallowed Inline Comment",
            "category": "comment",
            "dialect": "f77",
            "summary": "Fails in f2py because fixed-form .f files forbid trailing ! comments.",
        },
        {
            "id": "badcomment_implicit_f77",
            "filename": "badcomment_implicit.f",
            "title": "Fortran 77 Inline Comment (with implicit none)",
            "category": "comment",
            "dialect": "f77",
            "summary": "Has implicit none, but still fails f2py parser due to inline ! comment in .f file.",
        },
        {
            "id": "goodcomment_f77",
            "filename": "goodcomment.f",
            "title": "Fortran 77 Valid Full-Line Comment",
            "category": "comment",
            "dialect": "f77",
            "summary": "Uses full-line comment in fixed-form .f, though missing implicit none.",
        },
        {
            "id": "goodcomment_f90",
            "filename": "goodcomment.f90",
            "title": "Fortran 90 Free-Form Inline Comment",
            "category": "comment",
            "dialect": "f90",
            "summary": "Free-form .f90 permits inline ! comments.",
        },
        {
            "id": "badprec_f90",
            "filename": "badprec.f90",
            "title": "Kind Mapping & Literal Promotion (badprec.f90)",
            "category": "precision",
            "dialect": "f90",
            "summary": "Tests real64 kind mapping against .f2py_f2cmap and single-precision atan(1.) literal.",
        },
        {
            "id": "prod_f90",
            "filename": "prod.f90",
            "title": "Subroutine INTENT Comparison (prod.f90)",
            "category": "intent",
            "dialect": "f90",
            "summary": "Contrasts ProdNoIntent (missing intent) with ProdIntent, ProdInOut, and vector kernels.",
        },
        {
            "id": "float_precision_f90",
            "filename": "floatPrecision.f90",
            "title": "IEEE 754 Machine Epsilon Module (floatPrecision.f90)",
            "category": "precision",
            "dialect": "f90",
            "summary": "Computes 32-bit, 64-bit, and 128-bit float precision using sp, dp, and qp kinds.",
        },
    ]

    presets: List[Dict[str, Any]] = []
    for spec in preset_specs:
        fpath = SOURCE_DIR / spec["filename"]
        code = fpath.read_text(encoding="utf-8") if fpath.exists() else ""
        presets.append({**spec, "code": code})
    return presets


def audit_fortran_source(
    code: str,
    filename: str = "snippet.f90",
    cmap_mode: str = "modern",
) -> Dict[str, Any]:
    """
    Analyze Fortran source code for f2py compatibility, precision hazards, and
    INTENT completeness. Returns structured diagnostics and auto-remediated code.
    """
    is_f77 = filename.lower().endswith((".f", ".for", ".f77"))
    mapped_kinds = DEFAULT_CMAP_KINDS if cmap_mode == "modern" else LEGACY_CMAP_KINDS

    lines = code.splitlines()
    findings: List[Dict[str, Any]] = []
    fixed_lines: List[str] = list(lines)

    has_implicit_none = bool(re.search(r"\bimplicit\s+none\b", code, flags=re.IGNORECASE))
    if not has_implicit_none:
        findings.append(
            {
                "line": 1,
                "severity": "warning",
                "rule_id": "F2PY-IMPLICIT-01",
                "title": "Missing `implicit none` declaration",
                "message": (
                    "Without `implicit none`, undeclared variables default to single-precision "
                    "`real` or `integer` (I-N rule), hiding type mismatches in f2py wrappers."
                ),
                "suggestion": "Add `implicit none` immediately after the module/subroutine header.",
            }
        )

    # Check 1: Fortran 77 inline comments
    if is_f77:
        for idx, raw_line in enumerate(lines):
            stripped = raw_line.lstrip()
            if not stripped or stripped.startswith("!") or raw_line[:1] in ("c", "C", "*"):
                continue
            if "!" in raw_line:
                code_part, comment_part = raw_line.split("!", 1)
                if code_part.strip():
                    findings.append(
                        {
                            "line": idx + 1,
                            "severity": "danger",
                            "rule_id": "F2PY-F77-COMMENT",
                            "title": "Disallowed inline `!` comment in Fortran 77 (`.f`) file",
                            "message": (
                                f"Line {idx + 1} contains trailing comment `!{comment_part}`. "
                                "f2py enforces strict Fortran 77 fixed-form rules on `.f` files "
                                "and rejects inline comments."
                            ),
                            "suggestion": (
                                "Move the comment to its own full line above the statement, "
                                "or rename the file extension to `.f90`."
                            ),
                        }
                    )
                    fixed_lines[idx] = f"! {comment_part.strip()}\n{code_part.rstrip()}"

    # Check 2: Subroutine argument INTENT checks
    sub_pattern = re.compile(
        r"^\s*subroutine\s+([a-zA-Z0-9_]+)\s*(?:\(([^)]*)\))?",
        flags=re.IGNORECASE,
    )
    end_sub_pattern = re.compile(r"^\s*end\s+subroutine\b", flags=re.IGNORECASE)

    current_sub: Optional[str] = None
    current_args: List[str] = []
    current_sub_line: int = 1
    args_with_intent: set[str] = set()

    for idx, raw_line in enumerate(lines):
        clean_line = raw_line.split("!", 1)[0]
        m_sub = sub_pattern.match(clean_line)
        if m_sub:
            current_sub = m_sub.group(1)
            raw_args = m_sub.group(2) or ""
            current_args = [a.strip().lower() for a in raw_args.split(",") if a.strip()]
            current_sub_line = idx + 1
            args_with_intent = set()
            continue

        if current_sub is not None:
            if re.search(r"\bintent\s*\(\s*(?:in|out|inout|in\s*out)\s*\)", clean_line, flags=re.IGNORECASE):
                if "::" in clean_line:
                    decl_rhs = clean_line.split("::", 1)[1]
                    for token in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", decl_rhs):
                        args_with_intent.add(token.lower())

            if end_sub_pattern.match(clean_line):
                missing_args = [a for a in current_args if a not in args_with_intent]
                if missing_args:
                    findings.append(
                        {
                            "line": current_sub_line,
                            "severity": "warning",
                            "rule_id": "F2PY-INTENT-01",
                            "title": f"Subroutine `{current_sub}` has arguments without explicit `INTENT`",
                            "message": (
                                f"Arguments `{', '.join(missing_args)}` in `{current_sub}` lack `INTENT(...)`. "
                                "f2py defaults all unspecified arguments to `INTENT(IN)`, so any changes "
                                "assigned in Fortran are discarded and never returned to Python."
                            ),
                            "suggestion": (
                                "Declare `real, intent(in) :: ...` for inputs and "
                                "`real, intent(out) :: ...` for outputs."
                            ),
                        }
                    )
                current_sub = None

    # Check 3: Kind mapping and literal promotion checks
    kind_pattern = re.compile(r"\breal\s*\(\s*(?:kind\s*=\s*)?([a-zA-Z0-9_]+)\s*\)", flags=re.IGNORECASE)
    detected_kinds: set[str] = set()

    for idx, raw_line in enumerate(lines):
        clean_line = raw_line.split("!", 1)[0]
        for km in kind_pattern.finditer(clean_line):
            kind_name = km.group(1).lower()
            detected_kinds.add(kind_name)
            if kind_name not in mapped_kinds:
                findings.append(
                    {
                        "line": idx + 1,
                        "severity": "danger",
                        "rule_id": "F2PY-CMAP-01",
                        "title": f"Unmapped Fortran kind `{kind_name}` in `.f2py_f2cmap`",
                        "message": (
                            f"`real({kind_name})` is used on line {idx + 1}, but `{kind_name}` is "
                            f"not mapped in the active `.f2py_f2cmap` ({', '.join(sorted(mapped_kinds))}). "
                            "f2py silently downgrades unmapped `real` kinds to 32-bit `float32`."
                        ),
                        "suggestion": f"Add `'{kind_name}': 'double'` to `dict(real=...)` in `.f2py_f2cmap`.",
                    }
                )

        # Check for single-precision `atan(1.)` assigned to a 64-bit variable
        if re.search(r"real\s*\(\s*(?:real64|dp)\s*\)", clean_line, flags=re.IGNORECASE) and re.search(
            r"atan\s*\(\s*1\.0?\s*\)", clean_line, flags=re.IGNORECASE
        ):
            findings.append(
                {
                    "line": idx + 1,
                    "severity": "warning",
                    "rule_id": "F2PY-LITERAL-64",
                    "title": "Single-precision literal `atan(1.)` assigned to 64-bit variable",
                    "message": (
                        "In Fortran, `4*atan(1.)` is evaluated in 32-bit single precision (~7 digits) "
                        "before being widened to `real64`. The lower 29 mantissa bits are inaccurate."
                    ),
                    "suggestion": "Use explicit kind suffixes: `4.0_real64 * atan(1.0_real64)`.",
                }
            )
            fixed_lines[idx] = re.sub(
                r"4\s*\*\s*atan\s*\(\s*1\.0?\s*\)",
                "4.0_real64 * atan(1.0_real64)",
                fixed_lines[idx],
                flags=re.IGNORECASE,
            )

    if not has_implicit_none and fixed_lines:
        # Insert implicit none after first subroutine/module line
        inserted = False
        for idx, ln in enumerate(fixed_lines):
            if re.match(r"^\s*(?:module|subroutine|program)\b", ln.split("!", 1)[0], flags=re.IGNORECASE):
                indent = "      " if is_f77 else "  "
                fixed_lines.insert(idx + 1, f"{indent}implicit none")
                inserted = True
                break
        if not inserted:
            fixed_lines.insert(0, "implicit none")

    all_kinds = sorted(detected_kinds | {"sp", "dp", "real32", "real64"})
    cmap_entries = []
    for k in all_kinds:
        c_type = "float" if k in ("sp", "real32") else ("long_double" if k in ("qp", "real128") else "double")
        cmap_entries.append(f"'{k}': '{c_type}'")
    recommended_cmap = f"dict(real=dict({', '.join(cmap_entries)}))"

    danger_count = sum(1 for f in findings if f["severity"] == "danger")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")

    if danger_count > 0:
        overall_status = "danger"
        overall_label = f"{danger_count} Blocking Issue{'s' if danger_count > 1 else ''}"
    elif warning_count > 0:
        overall_status = "warning"
        overall_label = f"{warning_count} Advisory Warning{'s' if warning_count > 1 else ''}"
    else:
        overall_status = "success"
        overall_label = "f2py Ready"

    return {
        "filename": filename,
        "dialect": "Fortran 77 Fixed-Form (.f)" if is_f77 else "Fortran 90+ Free-Form (.f90)",
        "cmap_mode": cmap_mode,
        "overall_status": overall_status,
        "overall_label": overall_label,
        "danger_count": danger_count,
        "warning_count": warning_count,
        "detected_kinds": sorted(detected_kinds),
        "findings": findings,
        "fixed_code": "\n".join(fixed_lines) + "\n",
        "recommended_cmap": recommended_cmap,
    }
