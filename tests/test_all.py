from fastapi.testclient import TestClient
import numpy as np
import pytest
from pytest import approx

from badprec import badprec
from demof2py.app import app
from demof2py.auditor import (
    audit_fortran_source,
    build_jupyter_notebook,
    build_project_zip_bundle,
    generate_f2py_build_scaffold,
    load_project_presets,
    modernize_f77_to_f2008,
)
from demof2py.cli import main as cli_main
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

    x_traj, v_traj, final_energy = fortnumerics.rk4harmonicstep(100, 0.02, 2.0, 0.0, 1.0, 0.0)
    assert len(x_traj) == 101
    assert len(v_traj) == 101
    assert final_energy == approx(2.0, rel=1e-5)

    rhs2d = np.zeros((11, 11), dtype=np.float64, order="F")
    rhs2d[5, 5] = 100.0
    u_2d, max_res, l2_2d = fortnumerics.jacobipoisson2d(60, rhs2d)
    assert u_2d.shape == (11, 11)
    assert bool(u_2d.flags["F_CONTIGUOUS"]) is True
    assert float(u_2d[5, 5]) > 0.0
    assert l2_2d > 0.0


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

    num_f = client.post(
        "/api/v1/numerics/explore",
        json={
            "matrix_preset": "spd_stiffness",
            "order_mode": "F",
            "integrand": "poly_quartic",
            "points": 31,
        },
    )
    assert num_f.status_code == 200
    num_f_data = num_f.json()
    assert num_f_data["matrix"]["f_contiguous"] is True
    assert num_f_data["matrix"]["zero_copy_pass"] is True
    assert num_f_data["matrix"]["strides_bytes"] == [8, 24]
    assert num_f_data["matrix"]["max_abs_err_vs_blas"] < 1e-13
    assert num_f_data["quadrature"]["exact_value"] == approx(206.0 / 15.0)
    assert num_f_data["quadrature"]["simpson_abs_error"] < 1e-5
    assert num_f_data["quadrature"]["accuracy_gain_x"] > 100.0

    num_c = client.post(
        "/api/v1/numerics/explore",
        json={
            "matrix_preset": "hilbert_3x3",
            "order_mode": "C",
            "integrand": "exp_unit",
            "points": 51,
        },
    )
    assert num_c.status_code == 200
    num_c_data = num_c.json()
    assert num_c_data["matrix"]["f_contiguous"] is False
    assert num_c_data["matrix"]["zero_copy_pass"] is False
    assert num_c_data["matrix"]["strides_bytes"] == [24, 8]
    assert num_c_data["quadrature"]["exact_value"] == approx(np.e - 1.0)

    quad_resp = client.post(
        "/api/v1/numerics/quadratic",
        json={"a": 1.0, "b": 1.0e8, "c": 1.0},
    )
    assert quad_resp.status_code == 200
    quad_data = quad_resp.json()
    assert quad_data["r2_stable"] == approx(-1.0e-8, rel=1e-12)
    assert quad_data["mantissa_digits_lost"] > 6.0
    assert quad_data["vieta_stable_rel_error"] < 1e-14
    assert len(quad_data["sweep"]) == 5

    native_resp = client.post(
        "/api/v1/native-cli/run",
        json={"mode": "all"},
    )
    assert native_resp.status_code == 200
    native_data = native_resp.json()
    assert native_data["exit_code"] == 0
    assert "Fortran 2008 Numerical Workbench" in native_data["stdout"]

    rk4_resp = client.post(
        "/api/v1/ode/rk4",
        json={"steps": 100, "dt": 0.05, "omega0": 2.0, "zeta": 0.0},
    )
    assert rk4_resp.status_code == 200
    rk4_data = rk4_resp.json()
    assert rk4_data["energy_ratio"] == approx(1.0, rel=1e-4)

    pois_resp = client.post(
        "/api/v1/pde/poisson2d",
        json={"n": 15, "iterations": 80, "source_type": "dipole"},
    )
    assert pois_resp.status_code == 200
    pois_data = pois_resp.json()
    assert pois_data["f_contiguous"] is True
    assert pois_data["l2_norm"] > 0.0

    cc_bad = client.post(
        "/api/v1/diagnostics/compile-check",
        json={"code": "      subroutine f(x)\n      real x ! bad inline\n      end", "filename": "bad.f"},
    )
    assert cc_bad.status_code == 200
    assert cc_bad.json()["passed"] is False

    cc_good = client.post(
        "/api/v1/diagnostics/compile-check",
        json={"code": "subroutine f(x)\n  implicit none\n  real, intent(in) :: x\nend subroutine f\n", "filename": "good.f90"},
    )
    assert cc_good.status_code == 200
    assert cc_good.json()["passed"] is True

    eigen_resp = client.post(
        "/api/v1/linalg/eigen",
        json={"preset": "spd_stiffness", "iterations": 60},
    )
    assert eigen_resp.status_code == 200
    eigen_data = eigen_resp.json()
    assert eigen_data["abs_error_vs_lapack"] < 1e-10
    assert eigen_data["residual_norm"] < 1e-9
    assert len(eigen_data["eigenvector"]) == 3

    tridiag_resp = client.post(
        "/api/v1/linalg/tridiag",
        json={"n": 21, "bc_type": "catenary"},
    )
    assert tridiag_resp.status_code == 200
    tridiag_data = tridiag_resp.json()
    assert tridiag_data["residual_inf"] < 1e-11
    assert tridiag_data["max_err_vs_dense"] < 1e-11
    assert len(tridiag_data["solution_preview"]) == 9

    scaffold_resp = client.post(
        "/api/v1/diagnostics/scaffold",
        json={
            "code": "module fortnumerics\ncontains\nsubroutine f(x, y)\n  implicit none\n  real, intent(in) :: x\n  real, intent(out) :: y\n  y = x * 2.0\nend subroutine f\nend module fortnumerics\n",
            "filename": "numerics.f90",
            "module_name": "fortnumerics",
        },
    )
    assert scaffold_resp.status_code == 200
    scaf = scaffold_resp.json()
    assert "python module fortnumerics" in scaf["pyf_signature"]
    assert "py.extension_module" in scaf["meson_build"]
    assert "cmake_minimum_required" in scaf["cmake_lists"]
    assert "iso_c_binding" in scaf["c_binding_f90"]
    assert "ctypes.CDLL" in scaf["ctypes_wrapper_py"]
    assert "numpy.f2py" in scaf["cli_compile_cmd"]

    bs_resp = client.post(
        "/api/v1/quant/blackscholes",
        json={"n": 41, "strike": 100.0, "rate": 0.05, "sigma": 0.20, "maturity": 1.0},
    )
    assert bs_resp.status_code == 200
    bs_data = bs_resp.json()
    assert bs_data["atm_call"] == approx(10.45058357, rel=1e-6)
    assert bs_data["atm_put"] == approx(5.57352602, rel=1e-6)
    assert bs_data["max_put_call_parity_error"] < 1e-12

    mod_resp = client.post(
        "/api/v1/diagnostics/modernize",
        json={
            "code": "      subroutine legacy(x, y)\n      real*8 x, y\n      y = x * 2.0d0\n      end",
            "filename": "legacy.f",
        },
    )
    assert mod_resp.status_code == 200
    mod_data = mod_resp.json()
    assert mod_data["target_filename"] == "legacy.f90"
    assert "implicit none" in mod_data["modernized_code"]

    zip_resp = client.post(
        "/api/v1/diagnostics/bundle.zip",
        json={"code": "subroutine f(x)\n  implicit none\n  real, intent(in) :: x\nend subroutine f\n", "filename": "f.f90"},
    )
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert len(zip_resp.content) > 200

    nb_resp = client.get("/api/v1/export/notebook.ipynb")
    assert nb_resp.status_code == 200
    assert nb_resp.json()["nbformat"] == 4
    assert len(nb_resp.json()["cells"]) >= 3

    index_page = client.get("/")
    assert index_page.status_code == 200
    assert "f2py Workbench" in index_page.text


def test_v4_eigen_tridiag_scaffold_and_cli():
    a = np.array(
        [[4.0, -1.0, 0.0], [-1.0, 4.0, -1.0], [0.0, -1.0, 4.0]],
        dtype=np.float64,
        order="F",
    )
    eigval, eigvec, res_norm = fortnumerics.powereigen3x3(a, 80)
    assert eigval == approx(4.0 + np.sqrt(2.0), rel=1e-12)
    assert res_norm < 1e-11
    assert np.linalg.norm(eigvec) == approx(1.0, rel=1e-12)

    n = 15
    sub_d = np.full(n, -1.0, dtype=np.float64)
    sub_d[0] = 0.0
    main_d = np.full(n, 2.0, dtype=np.float64)
    super_d = np.full(n, -1.0, dtype=np.float64)
    super_d[-1] = 0.0
    rhs = np.ones(n, dtype=np.float64)
    x_out, res_inf = fortnumerics.thomastridiag(sub_d, main_d, super_d, rhs)
    assert len(x_out) == n
    assert res_inf < 1e-12

    presets = {p["filename"]: p for p in load_project_presets()}
    scaf = generate_f2py_build_scaffold(
        presets["numerics.f90"]["code"],
        filename="numerics.f90",
        module_name="fortnumerics",
    )
    assert scaf["module_name"] == "fortnumerics"
    assert "powereigen3x3" in scaf["pyi_stub"]
    assert "thomastridiag" in scaf["pyi_stub"]
    assert "py.extension_module" in scaf["meson_build"]
    assert "cmake_minimum_required" in scaf["cmake_lists"]

    assert cli_main(["eigen", "--preset", "spd_stiffness", "--iterations", "50"]) == 0
    assert cli_main(["tridiag", "-n", "15", "--bc", "catenary"]) == 0
    assert cli_main(["scaffold", "--preset", "numerics_f90"]) == 0


def test_v5_blackscholes_modernizer_bundle_and_notebook():
    s_grid = np.linspace(60.0, 140.0, 41, dtype=np.float64)
    c_price, p_price, c_delta = fortnumerics.blackscholesgrid(
        s_grid, 100.0, 0.05, 0.20, 1.0
    )
    assert c_price[20] == approx(10.45058357, rel=1e-6)
    assert p_price[20] == approx(5.57352602, rel=1e-6)
    assert c_delta[20] == approx(0.63683065, rel=1e-6)

    presets = {p["filename"]: p for p in load_project_presets()}
    mod = modernize_f77_to_f2008(presets["badcomment.f"]["code"], "badcomment.f")
    assert mod["target_filename"] == "badcomment.f90"
    assert mod["transformation_count"] >= 2
    assert "implicit none" in mod["modernized_code"]
    assert "bind(C" in mod["c_binding_f90"]
    assert "ctypes.CDLL" in mod["ctypes_wrapper_py"]

    zip_bytes = build_project_zip_bundle(
        presets["numerics.f90"]["code"],
        filename="numerics.f90",
        module_name="fortnumerics",
    )
    assert zip_bytes[:2] == b"PK"
    assert len(zip_bytes) > 500

    nb = build_jupyter_notebook()
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) >= 3

    assert cli_main(["blackscholes", "-n", "41", "--sigma", "0.20"]) == 0
    assert cli_main(["modernize", "--preset", "badcomment_f"]) == 0

