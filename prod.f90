module prod

use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64
implicit none

contains

Subroutine ProdNoIntent(x,y,z)
real x,y,z
! This subroutine will not pass result back to Python,
! since f2py assumes INTENT(IN) instead of INTENT(INOUT) like
! plain FORTRAN compilers
z = x * y

End Subroutine


Subroutine ProdIntent(x,y,z)
! This subroutine will pass result back to Python
! Note that intent(in) is not invincible, subroutines called by
! subroutines can modify the original variable IF the 2nd subroutine
! doesn't have Intent(in)
real,Intent(In) :: x,y
real,Intent(Out):: z

z = x * y

End Subroutine


Subroutine ProdInOut(x,y,z)
! This subroutine will pass result back to Python IN PLACE, not on the left-hand
! of the equals sign! Requires ndarray on inout variable even for scalar cases!
real, Intent(In) :: x,y
real, Intent(inout)  :: z
z = x * y
End Subroutine

Pure Real Function prodpure(x,y)
! Elemental & Pure functions require intent declaration
real, Intent(in) :: x,y

prodpure = x*y

End Function

Subroutine ProdVecIntent(n, x, y, z)
! Element-wise double-precision vector product with explicit INTENT(OUT)
integer, Intent(In) :: n
real(dp), Intent(In) :: x(n), y(n)
real(dp), Intent(Out) :: z(n)

z = x * y
End Subroutine

Subroutine ProdDotDp(n, x, y, dot_val)
! Double-precision dot product kernel
integer, Intent(In) :: n
real(dp), Intent(In) :: x(n), y(n)
real(dp), Intent(Out) :: dot_val

dot_val = dot_product(x, y)
End Subroutine

Subroutine ProdScaleInOut(n, scale_factor, z)
! In-place array scaling using INTENT(INOUT)
integer, Intent(In) :: n
real(dp), Intent(In) :: scale_factor
real(dp), Intent(InOut) :: z(n)

z = z * scale_factor
End Subroutine

end module prod

