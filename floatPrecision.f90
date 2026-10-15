module precision_mod
  use, intrinsic :: iso_fortran_env, only: sp=>real32, dp=>real64, qp=>real128
  implicit none

contains

  subroutine compute_precision(ps, eps32, pd, eps64, pq, eps128)
    integer, intent(out) :: ps, pd, pq
    real(sp), intent(out) :: eps32
    real(dp), intent(out) :: eps64
    real(qp), intent(out) :: eps128

    real(sp) :: s
    real(dp) :: d
    real(qp) :: q

    ! ----- single prec -------
    ps = 0
    s = 1._sp
    do while (s /= s + 1._sp)
      s = s * 2._sp
      ps = ps + 1
    end do
    eps32 = 2._sp**(-(ps - 1._sp))

    ! ----- double prec -------
    pd = 0
    d = 1._dp
    do while (d /= d + 1._dp)
      d = d * 2._dp
      pd = pd + 1
    end do
    eps64 = 2._dp**(-(pd - 1._dp))

    ! ----- quad prec -------
    pq = 0
    q = 1._qp
    do while (q /= q + 1._qp)
      q = q * 2._qp
      pq = pq + 1
    end do
    eps128 = 2._qp**(-(pq - 1._qp))
  end subroutine compute_precision

end module precision_mod

program float_precision_prog
  use, intrinsic :: iso_fortran_env, only: sp=>real32, dp=>real64, qp=>real128
  use precision_mod, only: compute_precision
  implicit none

  integer :: ps, pd, pq
  real(sp) :: eps32
  real(dp) :: eps64
  real(qp) :: eps128

  call compute_precision(ps, eps32, pd, eps64, pq, eps128)

  print *, 'bits of precision for 32-bit float', ps
  print *, 'machine epsilon: 32-bit float', eps32
  print *, 'bits of precision for 64-bit float', pd
  print *, 'machine epsilon: 64-bit float', eps64
  print *, 'bits of precision for 128-bit float', pq
  print *, 'machine epsilon: 128-bit float', eps128

end program float_precision_prog

