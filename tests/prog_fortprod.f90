! this program should return "6." for each scalar print and verify vector kernels

use, intrinsic :: iso_fortran_env, only: dp => real64
use prod
implicit none
real x,y
real znoint,zint,zinout,zpure
real(dp) :: vx(3), vy(3), vz(3), dot_res

x=3.
y=2.

call prodnointent(x,y,znoint)
print *, znoint

call prodintent(x,y,zint)
print *, zint

zinout=-1.
call prodinout(x,y,zinout)
print *,zinout

zpure = prodpure(x,y)
print *,zpure

vx = [1.0_dp, 2.0_dp, 3.0_dp]
vy = [4.0_dp, 5.0_dp, 6.0_dp]
call ProdVecIntent(3, vx, vy, vz)
call ProdDotDp(3, vx, vy, dot_res)
call ProdScaleInOut(3, 2.0_dp, vz)
print *, dot_res

end program

