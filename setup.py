from distutils.core import setup, Extension
from distutils.command.sdist import sdist as _sdist

"""Setup script for Python module for ULTRACAM files"""

try:
    from sdist import sdist
    cmdclass = {'sdist': sdist}
except:
    cmdclass = {}

setup(name='trm.drivers',
      version='0',
      packages = ['trm', 'trm.drivers'],
      scripts=['scripts/usdriver.py',],

      author='Tom Marsh',
      description="Python module for drivers ULTRACAM etc",
      author_email='t.r.marsh@warwick.ac.uk',
      url='http://www.astro.warwick.ac.uk/',
      cmdclass = cmdclass
      )
