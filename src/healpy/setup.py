#!/usr/bin/env python

# Bootstrap setuptools installation. We require setuptools >= 3.2 because of a
# bug in earlier versions regarding C++ sources generated with Cython. See:
#    https://pypi.python.org/pypi/setuptools/3.6#id171
try:
    import pkg_resources
    pkg_resources.require("setuptools >= 3.2")
except:
    from ez_setup import use_setuptools
    use_setuptools()

import os
from os.path import join
import errno
import fnmatch
import sys
import shlex
from distutils.sysconfig import get_config_var, get_config_vars
from setuptools import setup, Extension
from setuptools.command.test import test as TestCommand
from distutils.command.build_clib import build_clib
from distutils.errors import DistutilsExecError
from distutils.dir_util import mkpath
from distutils.file_util import copy_file
from distutils import log

# Apple switched default C++ standard libraries (from gcc's libstdc++ to
# clang's libc++), but some pre-packaged Python environments such as Anaconda
# are built against the old C++ standard library. Luckily, we don't have to
# actually detect which C++ standard library was used to build the Python
# interpreter. We just have to propagate MACOSX_DEPLOYMENT_TARGET from the
# configuration variables to the environment.
#
# This workaround fixes <https://github.com/healpy/healpy/issues/151>.
if get_config_var('MACOSX_DEPLOYMENT_TARGET') and not 'MACOSX_DEPLOYMENT_TARGET' in os.environ:
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = get_config_var('MACOSX_DEPLOYMENT_TARGET')

# For ReadTheDocs, do not build the extensions, only install .py files
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

cython_require = 'Cython >= 0.16'
try:
    if ('--help' in sys.argv[1:] or
        sys.argv[1] in ('--help-commands', 'egg_info', 'clean', '--version')):
        from distutils.command.build_ext import build_ext        
        ext = "c"
        extcpp = "cpp"
    else:
        pkg_resources.require(cython_require)
        from Cython.Distutils import build_ext
        ext = "pyx"
        extcpp = "pyx"
except:
    # User does not have a sufficiently new version of Cython.
    if os.path.exists('healpy/src/_query_disc.cpp'):
        # This source package already contains the Cython-generated sources,
        # so we can just use them.
        from distutils.command.build_ext import build_ext
        ext = "c"
        extcpp = "cpp"
    else:
        # This source does not contain the Cython-generated sources, so fail.
        raise DistutilsExecError('''

It looks like you are attempting to build from the Healpy development
sources, i.e., from GitHub. You need {0} to build Healpy from
development sources.

Either install Healpy from an official stable release from:
    https://pypi.python.org/pypi/healpy

OR, to build from development sources, first get {0} from:
    https://pypi.python.org/pypi/Cython'''.format(cython_require))
  
if on_rtd:
    numpy_inc = ''
else:
    if ('--help' in sys.argv[1:] or
        sys.argv[1] in ('--help-commands', 'egg_info', 'clean', '--version')):
        numpy_inc = ''
    else:
        from numpy import get_include
        numpy_inc = get_include()


class custom_build_ext(build_ext):
    def run(self):
        # If we were asked to build any C/C++ libraries, add the directory
        # where we built them to the include path. (It's already on the library
        # path.)
        if self.distribution.has_c_libraries():
            self.run_command('build_clib')
            build_clib = self.get_finalized_command('build_clib')
            for key, value in build_clib.build_args.items():
                for ext in self.extensions:
                    if not hasattr(ext, key) or getattr(ext, key) is None:
                        setattr(ext, key, value)
                    else:
                        getattr(ext, key).extend(value)
        build_ext.run(self)


class PyTest(TestCommand):
    """Custom Setuptools test command to run doctests with py.test. Based on
    http://pytest.org/latest/goodpractises.html#integration-with-setuptools-test-commands"""

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args.insert(0, '--doctest-modules')

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(self.test_args))


def get_version():
    context = {}
    try:
        execfile
    except NameError:
        exec(open('healpy/version.py').read(), context)
    else:
        execfile('healpy/version.py', context)
    return context['__version__']

healpy_pixel_lib_src = '_healpy_pixel_lib.cc'
healpy_spht_src = '_healpy_sph_transform_lib.cc'
healpy_fitsio_src = '_healpy_fitsio_lib.cc'

#start with base extension
pixel_lib = Extension('healpy._healpy_pixel_lib',
                      sources=[join('healpy','src', healpy_pixel_lib_src)],
                      include_dirs=[numpy_inc],
                      language='c++'
                      )

spht_lib = Extension('healpy._healpy_sph_transform_lib',
                     sources=[join('healpy','src', healpy_spht_src)],
                     include_dirs=[numpy_inc],
                     language='c++'
                     )

hfits_lib = Extension('healpy._healpy_fitsio_lib',
                      sources=[join('healpy','src', healpy_fitsio_src)],
                      include_dirs=[numpy_inc],
                      language='c++'
                      )

install_requires = ['matplotlib', 'numpy', 'six']

# Add install dependency on astropy, unless pyfits is already installed.
try:
    import pyfits
except ImportError:
    install_requires.append('astropy')

if on_rtd:
    cmdclass = {}
    extension_list = []
else:
    cmdclass = {
        'build_ext': custom_build_ext,
        'test': PyTest}

    extension_list = [pixel_lib, spht_lib, hfits_lib,
                      Extension("healpy._query_disc",
                                ['healpy/src/_query_disc.'+extcpp],
                                include_dirs=[numpy_inc],
                                language='c++'),
                      Extension("healpy._sphtools", 
                                ['healpy/src/_sphtools.'+extcpp],
                                include_dirs=[numpy_inc],
                                language='c++'),
                      Extension("healpy._pixelfunc", 
                                ['healpy/src/_pixelfunc.'+extcpp],
                                include_dirs=[numpy_inc],
                                language='c++'),
                      ]
    for e in extension_list[-3:]: #extra setup for Cython extensions
        e.pyrex_directives = {"embedsignature": True}

setup(name='healpy',
      version=get_version(),
      description='Healpix tools package for Python',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
          'Operating System :: POSIX',
          'Programming Language :: C++',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Visualization'
      ],
      author='C. Rosset, A. Zonca',
      author_email='cyrille.rosset@apc.univ-paris-diderot.fr',
      url='http://github.com/healpy',
      packages=['healpy','healpy.test'],
      py_modules=['healpy.pixelfunc','healpy.sphtfunc',
                  'healpy.visufunc','healpy.fitsfunc',
                  'healpy.projector','healpy.rotator',
                  'healpy.projaxes','healpy.version'],
      cmdclass = cmdclass,
      ext_modules = extension_list,
      package_data = {'healpy': ['data/*.fits', 'data/totcls.dat', 'test/data/*.fits', 'test/data/*.sh']},
      setup_requires=setup_requires,
      install_requires=install_requires,
      tests_require=['pytest'],
      test_suite='healpy',
      license='GPLv2'
      )
