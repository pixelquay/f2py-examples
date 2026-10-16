program fortran_workbench_cli
  !! Standalone native Fortran 2008 CLI application for running IEEE-754 precision
  !! diagnostics, F2PY intent semantics checks, 1D Heat Diffusion PDE simulation,
  !! column-major matrix multiplication, and Simpson numerical quadrature.
  use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64, qp => real128, output_unit
  use :: prod, only: ProdIntent, ProdPure, ProdInOut, ProdNoIntent, ProdVecIntent, ProdDotDp
  use :: badprec, only: pi32, pi64, pi64_true
  use :: precision_mod, only: compute_precision
  use :: fortnumerics, only: MatMulDp, Heat1DStep, SimpsonIntegrateDp, QuadraticRootsCompare, &
    Rk4HarmonicStep, JacobiPoisson2D
  use :: fortnumerics, only: PowerEigen3x3, ThomasTridiag, BlackScholesGrid, SpectralDftPower, &
    MonteCarloOptionDp
  use :: fortnumerics, only: AutoDiffRosenbrockDp, CsrSpmvDp, CrankNicolson1D, NewtonSystem2D
  implicit none

  character(len=64) :: arg
  integer :: argc
  logical :: run_all, run_prec, run_int, run_pde, run_la, run_quad, run_ode, run_pois
  logical :: run_eig, run_tri, run_bs, run_spec, run_mc, run_ad, run_csr, run_cn, run_nwt

  argc = command_argument_count()
  run_all = (argc == 0)
  run_prec = .false.
  run_int = .false.
  run_pde = .false.
  run_la = .false.
  run_quad = .false.
  run_ode = .false.
  run_pois = .false.
  run_eig = .false.
  run_tri = .false.
  run_bs = .false.
  run_spec = .false.
  run_mc = .false.
  run_ad = .false.
  run_csr = .false.
  run_cn = .false.
  run_nwt = .false.

  if (argc > 0) then
    call get_command_argument(1, arg)
    select case (trim(arg))
    case ('--all', '-a')
      run_all = .true.
    case ('--precision', '-p')
      run_prec = .true.
    case ('--intents', '-i')
      run_int = .true.
    case ('--pde', '-h1d')
      run_pde = .true.
    case ('--linalg', '-m')
      run_la = .true.
    case ('--quad', '-q')
      run_quad = .true.
    case ('--ode', '-o')
      run_ode = .true.
    case ('--poisson', '-2d')
      run_pois = .true.
    case ('--eigen', '-e')
      run_eig = .true.
    case ('--tridiag', '-t')
      run_tri = .true.
    case ('--blackscholes', '-bs')
      run_bs = .true.
    case ('--spectral', '-sp')
      run_spec = .true.
    case ('--montecarlo', '-mc')
      run_mc = .true.
    case ('--autodiff', '-ad')
      run_ad = .true.
    case ('--sparse', '-csr')
      run_csr = .true.
    case ('--cranknicolson', '-cn')
      run_cn = .true.
    case ('--newton', '-nr')
      run_nwt = .true.
    case ('--help', '-h')
      call print_usage()
      stop 0
    case default
      run_all = .true.
    end select
  end if

  write(output_unit, '(a)') '===================================================================='
  write(output_unit, '(a)') '  Fortran 2008 Standalone Numerical Workbench & F2PY Bridge Suite   '
  write(output_unit, '(a)') '===================================================================='

  if (run_all .or. run_prec) call section_precision()
  if (run_all .or. run_int)  call section_intents()
  if (run_all .or. run_pde)  call section_heat_pde()
  if (run_all .or. run_la)   call section_linalg()
  if (run_all .or. run_quad) call section_quadrature()
  if (run_all .or. run_ode)  call section_ode()
  if (run_all .or. run_pois) call section_poisson()
  if (run_all .or. run_eig)  call section_eigen()
  if (run_all .or. run_tri)  call section_tridiag()
  if (run_all .or. run_bs)   call section_blackscholes()
  if (run_all .or. run_spec) call section_spectral()
  if (run_all .or. run_mc)   call section_montecarlo()
  if (run_all .or. run_ad)   call section_autodiff()
  if (run_all .or. run_csr)  call section_sparse()
  if (run_all .or. run_cn)   call section_crank_nicolson()
  if (run_all .or. run_nwt)  call section_newton()

contains

  subroutine print_usage()
    write(output_unit, '(a)') 'Usage: fortran_workbench [--all | --precision | --intents | --pde |' // &
      ' --linalg | --quad | --ode | --poisson | --eigen | --tridiag | --blackscholes |' // &
      ' --spectral | --montecarlo | --autodiff | --sparse | --cranknicolson | --newton]'
  end subroutine print_usage


  subroutine section_precision()
    real(sp) :: eps32
    real(dp) :: eps64
    real(qp) :: eps128
    integer :: bits32, bits64, bits128
    real(dp) :: r1_naive, r2_naive, r1_stable, r2_stable, cancel_err

    call compute_precision(bits32, eps32, bits64, eps64, bits128, eps128)
    call QuadraticRootsCompare(1.0_dp, 1.0e8_dp, 1.0_dp, r1_naive, r2_naive, r1_stable, r2_stable, cancel_err)

    write(output_unit, '(/,a)') '[1] IEEE-754 Precision & Literal Kind Audit'
    write(output_unit, '(a,i4,a,es14.6)') '  real32 bits: ', bits32, '  epsilon: ', eps32
    write(output_unit, '(a,i4,a,es14.6)') '  real64 bits: ', bits64, '  epsilon: ', eps64
    write(output_unit, '(a,f20.16)')      '  pi32 (single literal):       ', real(pi32, dp)
    write(output_unit, '(a,f20.16)')      '  pi64 (untyped literal trap): ', pi64
    write(output_unit, '(a,f20.16)')      '  pi64_true (4*atan(1.0_dp)):  ', pi64_true
    write(output_unit, '(a,es14.6)')      '  Quadratic Citardauq delta:   ', cancel_err
  end subroutine section_precision


  subroutine section_intents()
    real(sp) :: x, y, z_out, z_pure, z_inout
    real(dp) :: vx(4), vy(4), vz(4), dot_res

    x = 3.0_sp
    y = 4.0_sp
    z_inout = 23456.0_sp

    call ProdIntent(x, y, z_out)
    z_pure = ProdPure(x, y)
    call ProdInOut(x, y, z_inout)

    vx = [1.0_dp, 2.0_dp, 3.0_dp, 4.0_dp]
    vy = [2.0_dp, 3.0_dp, 4.0_dp, 5.0_dp]
    call ProdVecIntent(4, vx, vy, vz)
    call ProdDotDp(4, vx, vy, dot_res)

    write(output_unit, '(/,a)') '[2] F2PY Intent & Vector Kernel Verification'
    write(output_unit, '(a,f10.4)') '  ProdIntent(3, 4)   -> ', z_out
    write(output_unit, '(a,f10.4)') '  ProdPure(3, 4)     -> ', z_pure
    write(output_unit, '(a,f10.4)') '  ProdInOut(3, 4)    -> ', z_inout
    write(output_unit, '(a,f10.4)') '  ProdDotDp(vx, vy)  -> ', dot_res
  end subroutine section_intents


  subroutine section_heat_pde()
    integer, parameter :: n = 21, steps = 25
    real(dp) :: u_init(n), u_final(n), x_coord, dx, dt, alpha, cfl, l2_norm
    integer :: i

    dx = 1.0_dp / real(n - 1, dp)
    alpha = 0.01_dp
    dt = 0.1_dp
    do i = 1, n
      x_coord = real(i - 1, dp) * dx
      u_init(i) = sin(3.14159265358979323846_dp * x_coord)
    end do

    call Heat1DStep(n, steps, alpha, dx, dt, u_init, u_final, cfl, l2_norm)

    write(output_unit, '(/,a)') '[3] 1D Heat Diffusion PDE Stencil (du/dt = alpha * d^2u/dx^2)'
    write(output_unit, '(a,f10.4,a,f10.6,a,f10.6)') &
      '  CFL Number: ', cfl, '  Peak Center u(0.5): ', u_final((n + 1) / 2), '  L2 Norm: ', l2_norm
  end subroutine section_heat_pde


  subroutine section_linalg()
    real(dp) :: a(2, 2), b(2, 2), c(2, 2)

    a = reshape([1.0_dp, 3.0_dp, 2.0_dp, 4.0_dp], [2, 2])
    b = reshape([5.0_dp, 7.0_dp, 6.0_dp, 8.0_dp], [2, 2])
    call MatMulDp(2, 2, 2, a, b, c)

    write(output_unit, '(/,a)') '[4] Column-Major Matrix Product (MatMulDp 2x2)'
    write(output_unit, '(a,2f8.2,a,2f8.2)') '  Row 1: ', c(1, 1), c(1, 2), ' | Row 2: ', c(2, 1), c(2, 2)
  end subroutine section_linalg


  subroutine section_quadrature()
    integer, parameter :: n = 101
    real(dp) :: y(n), dx, x_val, integral, exact_val
    integer :: i

    dx = 3.14159265358979323846_dp / real(n - 1, dp)
    do i = 1, n
      x_val = real(i - 1, dp) * dx
      y(i) = sin(x_val)
    end do

    call SimpsonIntegrateDp(n, dx, y, integral)
    exact_val = 2.0_dp

    write(output_unit, '(/,a)') '[5] Composite Simpson Quadrature int_0^pi sin(x) dx'
    write(output_unit, '(a,f16.12,a,es12.4)') '  Integral: ', integral, '  Abs Error: ', abs(integral - exact_val)
  end subroutine section_quadrature


  subroutine section_ode()
    integer, parameter :: steps = 100
    real(dp) :: x_traj(steps + 1), v_traj(steps + 1), final_energy

    call Rk4HarmonicStep(steps, 0.05_dp, 2.0_dp, 0.15_dp, 1.0_dp, 0.0_dp, x_traj, v_traj, final_energy)
    write(output_unit, '(/,a)') '[6] 4th-Order Runge-Kutta (RK4) Damped Oscillator (Rk4HarmonicStep)'
    write(output_unit, '(a,f12.6,a,f12.6,a,es12.4)') &
      '  x(T): ', x_traj(steps + 1), '  v(T): ', v_traj(steps + 1), '  Final Energy: ', final_energy
  end subroutine section_ode


  subroutine section_poisson()
    integer, parameter :: n = 15, iters = 60
    real(dp) :: rhs(n, n), u_out(n, n), max_res, l2_norm

    rhs = 0.0_dp
    rhs((n + 1) / 2, (n + 1) / 2) = 100.0_dp
    call JacobiPoisson2D(n, iters, rhs, u_out, max_res, l2_norm)

    write(output_unit, '(/,a)') '[7] 2D Poisson PDE Jacobi Relaxation (JacobiPoisson2D)'
    write(output_unit, '(a,f12.6,a,es12.4,a,f12.6)') &
      '  Center Potential: ', u_out((n + 1) / 2, (n + 1) / 2), '  Max Residual: ', max_res, '  L2 Norm: ', l2_norm
  end subroutine section_poisson


  subroutine section_eigen()
    real(dp) :: a(3, 3), eigval, eigvec(3), res_norm

    a = reshape([ &
      4.0_dp, -1.0_dp,  0.0_dp, &
     -1.0_dp,  4.0_dp, -1.0_dp, &
      0.0_dp, -1.0_dp,  4.0_dp  &
    ], [3, 3])
    call PowerEigen3x3(a, 30, eigval, eigvec, res_norm)

    write(output_unit, '(/,a)') '[8] Rayleigh-Quotient Dominant Eigenpair (PowerEigen3x3)'
    write(output_unit, '(a,f12.6,a,es12.4)') &
      '  Dominant Eigenvalue lambda_max: ', eigval, '  Residual ||Av - lambda v||_2: ', res_norm
  end subroutine section_eigen


  subroutine section_tridiag()
    integer, parameter :: n = 5
    real(dp) :: sub_d(n), main_d(n), super_d(n), rhs(n), x_out(n), res_inf

    sub_d   = [0.0_dp, -1.0_dp, -1.0_dp, -1.0_dp, -1.0_dp]
    main_d  = [2.0_dp,  2.0_dp,  2.0_dp,  2.0_dp,  2.0_dp]
    super_d = [-1.0_dp, -1.0_dp, -1.0_dp, -1.0_dp, 0.0_dp]
    rhs     = [1.0_dp,  0.0_dp,  0.0_dp,  0.0_dp,  1.0_dp]

    call ThomasTridiag(n, sub_d, main_d, super_d, rhs, x_out, res_inf)

    write(output_unit, '(/,a)') '[9] O(N) Thomas Tridiagonal Solver (ThomasTridiag)'
    write(output_unit, '(a,f12.6,a,es12.4)') &
      '  Center Solution x(3): ', x_out(3), '  Max Residual ||Tx - b||_inf: ', res_inf
  end subroutine section_tridiag


  subroutine section_blackscholes()
    integer, parameter :: n = 5
    real(dp) :: s_grid(n), call_p(n), put_p(n), delta_c(n)

    s_grid = [80.0_dp, 90.0_dp, 100.0_dp, 110.0_dp, 120.0_dp]
    call BlackScholesGrid(n, s_grid, 100.0_dp, 0.05_dp, 0.25_dp, 1.0_dp, call_p, put_p, delta_c)

    write(output_unit, '(/,a)') '[10] Vectorized do concurrent Black-Scholes Grid (BlackScholesGrid)'
    write(output_unit, '(a,f10.4,a,f10.4,a,f10.4)') &
      '  ATM (S=100, K=100): Call=', call_p(3), '  Put=', put_p(3), '  Delta=', delta_c(3)
  end subroutine section_blackscholes


  subroutine section_spectral()
    integer, parameter :: n = 64
    real(dp) :: sig(n), power_out(n / 2 + 1), peak_pow
    integer :: i, peak_bin
    real(dp), parameter :: two_pi = 6.28318530717958647692_dp

    do i = 1, n
      sig(i) = 1.2_dp * sin(two_pi * 5.0_dp * real(i - 1, dp) / real(n, dp)) + &
               0.5_dp * cos(two_pi * 12.0_dp * real(i - 1, dp) / real(n, dp))
    end do

    call SpectralDftPower(n, sig, power_out, peak_bin, peak_pow)

    write(output_unit, '(/,a)') '[11] Hann-Windowed Spectral DFT Power Spectrum (SpectralDftPower)'
    write(output_unit, '(a,i4,a,f10.4)') &
      '  Dominant Bin k*: ', peak_bin, '  Peak Power P(k*): ', peak_pow
  end subroutine section_spectral


  subroutine section_montecarlo()
    integer, parameter :: n_paths = 10000
    real(dp) :: call_est, put_est, std_err, paths_sample(64)

    call MonteCarloOptionDp(n_paths, 100.0_dp, 100.0_dp, 0.05_dp, 0.25_dp, 1.0_dp, 42, &
      call_est, put_est, std_err, paths_sample)

    write(output_unit, '(/,a)') '[12] Antithetic Box-Muller Monte Carlo Option Pricer (MonteCarloOptionDp)'
    write(output_unit, '(a,f10.4,a,f10.4,a,f10.4)') &
      '  MC Call: ', call_est, '  MC Put: ', put_est, '  Std Error: ', std_err
  end subroutine section_montecarlo


  subroutine section_autodiff()
    integer, parameter :: n_steps = 15
    real(dp) :: h_steps(n_steps), fd_fwd(n_steps), fd_cen(n_steps)
    real(dp) :: gx, gy, fval, opt_h
    integer :: i

    do i = 1, n_steps
      h_steps(i) = 10.0_dp ** (-real(i, dp))
    end do

    call AutoDiffRosenbrockDp(-1.2_dp, 1.0_dp, n_steps, h_steps, fd_fwd, fd_cen, gx, gy, fval, opt_h)

    write(output_unit, '(/,a)') '[13] Forward-Mode Dual-Number Auto-Diff vs FD V-Curve (AutoDiffRosenbrockDp)'
    write(output_unit, '(a,f10.4,a,f10.4,a,es10.2)') &
      '  Exact Grad: (', gx, ', ', gy, ')  Optimal Central h*: ', opt_h
  end subroutine section_autodiff


  subroutine section_sparse()
    integer, parameter :: n = 5, nnz = 13
    integer :: row_ptr(n + 1), col_idx(nnz)
    real(dp) :: vals(nnz), x(n), y_sparse(n), max_err, comp_ratio

    row_ptr = [1, 3, 6, 9, 12, 14]
    col_idx = [1, 2, 1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5]
    vals    = [2.0_dp, -1.0_dp, -1.0_dp, 2.0_dp, -1.0_dp, -1.0_dp, 2.0_dp, -1.0_dp, -1.0_dp, 2.0_dp, -1.0_dp, -1.0_dp, 2.0_dp]
    x       = [1.0_dp, 2.0_dp, 3.0_dp, 2.0_dp, 1.0_dp]

    call CsrSpmvDp(n, nnz, row_ptr, col_idx, vals, x, y_sparse, max_err, comp_ratio)

    write(output_unit, '(/,a)') '[14] Compressed Sparse Row (CSR) SpMV Kernel (CsrSpmvDp)'
    write(output_unit, '(a,f10.4,a,f8.2,a,es10.2)') &
      '  Center y(3): ', y_sparse(3), '  Compression Ratio: ', comp_ratio, 'x  Dense Diff: ', max_err
  end subroutine section_sparse


  subroutine section_crank_nicolson()
    integer, parameter :: n = 41, steps = 30
    real(dp) :: u_init(n), u_final(n), dx, dt, alpha, cfl, max_err, x_coord
    integer :: i

    dx = 1.0_dp / real(n - 1, dp)
    alpha = 0.02_dp
    dt = 0.05_dp
    do i = 1, n
      x_coord = real(i - 1, dp) * dx
      u_init(i) = sin(3.14159265358979323846_dp * x_coord)
    end do

    call CrankNicolson1D(n, steps, alpha, dx, dt, u_init, u_final, cfl, max_err)

    write(output_unit, '(/,a)') '[15] Unconditionally Stable Implicit Crank-Nicolson 1D Heat PDE (CrankNicolson1D)'
    write(output_unit, '(a,f10.4,a,f10.6,a,es10.2)') &
      '  CFL Number: ', cfl, '  Center u(0.5): ', u_final((n + 1) / 2), '  Max Analytical Err: ', max_err
  end subroutine section_crank_nicolson


  subroutine section_newton()
    integer, parameter :: max_iters = 15
    real(dp) :: x_root, y_root, traj_x(max_iters + 1), traj_y(max_iters + 1), res_hist(max_iters + 1)
    integer :: iters_taken

    call NewtonSystem2D(1.2_dp, 1.2_dp, 1.0_dp, max_iters, 1.0e-14_dp, &
      x_root, y_root, traj_x, traj_y, res_hist, iters_taken)

    write(output_unit, '(/,a)') '[16] 2D Coupled Nonlinear Newton-Raphson Solver (NewtonSystem2D)'
    write(output_unit, '(a,f10.6,a,f10.6,a,i3,a,es10.2)') &
      '  Root: (', x_root, ', ', y_root, ')  Iterations: ', iters_taken, '  Final ||F||_2: ', res_hist(iters_taken + 1)
  end subroutine section_newton

end program fortran_workbench_cli
