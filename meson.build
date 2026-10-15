project('f2py-examples', 'fortran',
  version : '2.0.0',
  default_options : ['default_library=static', 'buildtype=release'])

prod_lib = library('prod', 'prod.f90')
badprec_lib = library('badprec', 'badprec.f90')

prod_test_exe = executable('prod_test', 'tests/prog_fortprod.f90',
  link_with: prod_lib)

floatprec_exe = executable('float_precision', 'floatPrecision.f90')

test('fortran_prod_test', prod_test_exe)
test('fortran_float_precision', floatprec_exe)

