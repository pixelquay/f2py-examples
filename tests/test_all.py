from fastapi.testclient import TestClient
import numpy as np
import pytest
from pytest import approx

from badprec import badprec
from demof2py.app import app
from demof2py.auditor import audit_fortran_source, load_project_presets
from demof2py.precision import run_ieee754_benchmark
from fortnumerics import fortnumerics
from pyprod import prod


def test_main():
    x = 3
    y = 2
    # %%
    zint = prod.prodintent(x, y)
    assert zint == x * y
    assert isinstance(zint, float)  # f2py casts int => float
    # %%
    znoint = 12345.0
    znointent = prod.prodnointent(x, y, znoint)
    assert znointent is None
    # unmodified due to f2py intent(in) by default
    assert znoint == approx(12345.0)
    # %%
    zpure = prod.prodpure(x, y)
    assert zpure == x * y
    # %%
    # MUST be an ndarray e.g. 0d ndarray for scalar case!
    zinout = np.array(23456.0)
    prod.prodinout(x, y, zinout)
    assert zinout == x * y


def test_vector_kernels_and_inout_guard():
    vx = np.array([1.5, 2.5, 3.5], dtype=np.float64)
    vy = np.array([2.0, 4.0, 6.0], dtype=np.float64)

    vz = prod.prodvecintent(vx, vy)
    assert vz.dtype == np.float64
    assert np.allclose(vz, [3.0, 10.0, 21.0])

    dot_val = prod.proddotdp(vx, vy)
    assert dot_val == approx(34.0)

    scale_buf = np.array([2.0, 4.0, 8.0], dtype=np.float64)
    prod.prodscaleinout(0.5, scale_buf)
    assert np.allclose(scale_buf, [1.0, 2.0, 4.0])

    with pytest.raises(TypeError, match="INTENT\\(INOUT\\)"):
        prod.prodinout(3.0, 2.0, 123.0)  # type: ignore[arg-type]


def test_fortnumerics_linalg_pde_quadrature_and_quadratic():
    a = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64, order="F")
    b = np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float64, order="F")
    c = fortnumerics.matmuldp(a, b)
    assert np.allclose(c, [[19.0, 22.0], [43.0, 50.0]])

    grid = np.linspace(0.0, np.pi, 101, dtype=np.float64)
    dx = float(np.pi / 100.0)
    integral = fortnumerics.simpsonintegratedp(dx, np.sin(grid))
    assert integral == approx(2.0, abs=1e-7)

    u0 = np.sin(np.linspace(0.0, np.pi, 21, dtype=np.float64))
    u_final, cfl, l2_norm = fortnumerics.heat1dstep(15, 0.01, 0.05, 0.05, u0)
    assert cfl == approx(0.2)
    assert l2_norm > 0.0
    assert float(np.max(u_final)) < float(np.max(u0))

    r1_n, r2_n, r1_s, r2_s, cancel_err = fortnumerics.quadraticrootscompare(1.0, 1.0e8, 1.0)
    assert r1_s == approx(-1.0e8, rel=1e-12)
    assert r2_s == approx(-1.0e-8, rel=1e-12)
    assert cancel_err >= 0.0


def test_precision_and_cmap():
    assert badprec.pi32 == approx(3.1415927, rel=1e-6)
    assert abs(float(badprec.pi64_true) - np.pi) < 1e-15
    assert abs(float(badprec.pi64) - np.pi) > 1e-8  # single-prec literal promotion loss

    bench = run_ieee754_benchmark()
    tiers = {t["id"]: t for t in bench["tiers"]}
    assert tiers["float16"]["mantissa_bits"] == 11
    assert tiers["float32"]["mantissa_bits"] == 24
    assert tiers["float64"]["mantissa_bits"] == 53
    assert tiers["float128"]["mantissa_bits"] == 113


def test_fortran_auditor_rules():
    presets = {p["filename"]: p for p in load_project_presets()}
    assert "badcomment.f" in presets
    assert "goodcomment.f90" in presets
    assert "numerics.f90" in presets

    bad_f77 = audit_fortran_source(presets["badcomment.f"]["code"], "badcomment.f")
    assert bad_f77["overall_status"] == "danger"
    rule_ids = {f["rule_id"] for f in bad_f77["findings"]}
    assert "F2PY-F77-COMMENT" in rule_ids

    fixed_res = audit_fortran_source(bad_f77["fixed_code"], "badcomment.f")
    assert "F2PY-F77-COMMENT" not in {f["rule_id"] for f in fixed_res["findings"]}

    legacy_cmap_audit = audit_fortran_source(
        presets["badprec.f90"]["code"], "badprec.f90", cmap_mode="legacy"
    )
    assert "F2PY-CMAP-01" in {f["rule_id"] for f in legacy_cmap_audit["findings"]}

    numerics_audit = audit_fortran_source(presets["numerics.f90"]["code"], "numerics.f90")
    assert numerics_audit["overall_status"] == "success"
    assert "def heat1dstep(" in numerics_audit["generated_pyi_stub"]
    assert "python module fortnumerics" in numerics_audit["generated_pyf_signature"]


def test_fastapi_workbench_endpoints():
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    comp = client.post(
        "/api/v1/compute/prod",
        json={"kernel_id": "prodintent", "x": 4.0, "y": 5.0, "compare_all": True},
    )
    assert comp.status_code == 200
    payload = comp.json()
    assert payload["primary"]["return_value"] == approx(20.0)
    assert len(payload["comparison"]["results"]) == 6

    err_resp = client.post(
        "/api/v1/compute/prod",
        json={"kernel_id": "prodinout", "x": 3.0, "y": 2.0, "use_ndarray_for_inout": False},
    )
    assert err_resp.status_code == 400

    prec = client.get("/api/v1/precision/ieee754")
    assert prec.status_code == 200
    assert len(prec.json()["tiers"]) == 4

    bench_resp = client.post(
        "/api/v1/benchmarks/run",
        json={"workload": "simpson_quad", "size": 501, "iterations": 5},
    )
    assert bench_resp.status_code == 200
    assert len(bench_resp.json()["series"]) == 3

    pde_resp = client.post(
        "/api/v1/pde/simulate",
        json={"n": 31, "steps": 25, "alpha": 0.01, "pulse_type": "gaussian"},
    )
    assert pde_resp.status_code == 200
    assert pde_resp.json()["is_stable"] is True

    exp_resp = client.get("/api/v1/export/report")
    assert exp_resp.status_code == 200
    assert "heat_pde" in exp_resp.json()

    index_page = client.get("/")
    assert index_page.status_code == 200
    assert "f2py Workbench" in index_page.text
