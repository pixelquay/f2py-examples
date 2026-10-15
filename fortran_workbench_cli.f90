program fortran_workbench_cli
  !! Standalone native Fortran 2008 CLI application for running IEEE-754 precision
  !! diagnostics, F2PY intent semantics checks, 1D Heat Diffusion PDE simulation,
  !! column-major matrix multiplication, and Simpson numerical quadrature.
  use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64, output_unit
  use :: prod, only: ProdIntent, ProdPure, ProdInOut, ProdNoIntent, ProdVecIntent, ProdDotDp
  use :: badprec, only: pi32, pi64, pi64_true
  use :: precision_mod, only: compute_precision
  use :: fortnumerics, only: MatMulDp, Heat1DStep, SimpsonIntegrateDp, QuadraticRootsCompare, Rk4HarmonicStep, JacobiPoisson2D
  implicit none

  character(len=64) :: arg
  integer :: argc
  logical :: run_all, run_prec, run_int, run_pde, run_la, run_quad, run_ode, run_pois

  argc = command_argument_count()
  run_all = (argc == 0)
  run_prec = .false.
  run_int = .false.
  run_pde = .false.
  run_la = .false.
  run_quad = .false.
  run_ode = .false.
  run_pois = .false.

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

contains

  subroutine print_usage()
    write(output_unit, '(a)') 'Usage: fortran_workbench [--all | --precision | --intents | --pde | --linalg | --quad | --ode | --poisson]'
  end subroutine print_usage


  subroutine section_precision()
    real(sp) :: eps32, huge32, tiny32
    real(dp) :: eps64, huge64, tiny64
    integer :: bits32, bits64
    real(dp) :: r1_naive, r2_naive, r1_stable, r2_stable, cancel_err

    call compute_precision(eps32, eps64, huge32, huge64, tiny32, tiny64, bits32, bits64)
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

end program fortran_workbench_cli

