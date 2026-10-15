module fortnumerics
  !! Production Fortran 2008 numerical linear algebra, PDE stencil,
  !! composite quadrature, and floating-point stability routines for F2PY.
  use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64
  implicit none
  private
  public :: MatMulDp, Heat1DStep, SimpsonIntegrateDp, QuadraticRootsCompare

contains

  subroutine MatMulDp(m, k, n, a, b, c)
    !! Column-major (j-l-i) cache-optimized double-precision matrix product C = A * B.
    integer, intent(in) :: m, k, n
    real(dp), intent(in) :: a(m, k), b(k, n)
    real(dp), intent(out) :: c(m, n)
    integer :: i, j, l

    c = 0.0_dp
    do j = 1, n
      do l = 1, k
        do i = 1, m
          c(i, j) = c(i, j) + a(i, l) * b(l, j)
        end do
      end do
    end do
  end subroutine MatMulDp


  subroutine Heat1DStep(n, steps, alpha, dx, dt, u_init, u_final, cfl_number, l2_energy)
    !! 1D Heat Diffusion PDE solver: du/dt = alpha * d^2u/dx^2
    !! Uses explicit forward-Euler in time and 2nd-order central difference in space
    !! with fixed Dirichlet boundary conditions u(1) = u_init(1), u(n) = u_init(n).
    integer, intent(in) :: n, steps
    real(dp), intent(in) :: alpha, dx, dt
    real(dp), intent(in) :: u_init(n)
    real(dp), intent(out) :: u_final(n)
    real(dp), intent(out) :: cfl_number, l2_energy
    real(dp) :: u_curr(n), u_next(n)
    integer :: i, s

    cfl_number = alpha * dt / (dx * dx)
    u_curr = u_init
    u_next = u_init

    do s = 1, steps
      u_next(1) = u_curr(1)
      do i = 2, n - 1
        u_next(i) = u_curr(i) + cfl_number * (u_curr(i - 1) - 2.0_dp * u_curr(i) + u_curr(i + 1))
      end do
      u_next(n) = u_curr(n)
      u_curr = u_next
    end do

    u_final = u_curr
    l2_energy = sqrt(sum(u_final * u_final) * dx)
  end subroutine Heat1DStep


  subroutine SimpsonIntegrateDp(n, dx, y, integral)
    !! Composite Simpson's 1/3 quadrature rule (with trapezoidal tail if n is even).
    integer, intent(in) :: n
    real(dp), intent(in) :: dx
    real(dp), intent(in) :: y(n)
    real(dp), intent(out) :: integral
    integer :: i, m_odd
    real(dp) :: acc

    if (n < 2) then
      integral = 0.0_dp
      return
    else if (n == 2) then
      integral = 0.5_dp * dx * (y(1) + y(2))
      return
    end if

    m_odd = n
    acc = 0.0_dp
    if (mod(n, 2) == 0) then
      acc = 0.5_dp * dx * (y(n - 1) + y(n))
      m_odd = n - 1
    end if

    integral = y(1) + y(m_odd)
    do i = 2, m_odd - 1, 2
      integral = integral + 4.0_dp * y(i)
    end do
    do i = 3, m_odd - 2, 2
      integral = integral + 2.0_dp * y(i)
    end do
    integral = (dx / 3.0_dp) * integral + acc
  end subroutine SimpsonIntegrateDp


  subroutine QuadraticRootsCompare(a, b, c, r1_naive, r2_naive, r1_stable, r2_stable, cancel_err)
    !! Compares standard quadratic formula against numerically stable Citardauq root
    !! calculation to demonstrate catastrophic cancellation when b^2 >> 4ac.
    real(dp), intent(in) :: a, b, c
    real(dp), intent(out) :: r1_naive, r2_naive
    real(dp), intent(out) :: r1_stable, r2_stable
    real(dp), intent(out) :: cancel_err
    real(dp) :: disc, sqrt_disc, q

    disc = max(0.0_dp, b * b - 4.0_dp * a * c)
    sqrt_disc = sqrt(disc)

    r1_naive = (-b - sqrt_disc) / (2.0_dp * a)
    r2_naive = (-b + sqrt_disc) / (2.0_dp * a)

    if (b >= 0.0_dp) then
      q = -0.5_dp * (b + sqrt_disc)
      r1_stable = q / a
      r2_stable = c / q
    else
      q = -0.5_dp * (b - sqrt_disc)
      r1_stable = c / q
      r2_stable = q / a
    end if

    cancel_err = max(abs(r1_naive - r1_stable), abs(r2_naive - r2_stable))
  end subroutine QuadraticRootsCompare

end module fortnumerics
