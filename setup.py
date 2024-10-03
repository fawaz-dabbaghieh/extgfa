#!/usr/bin/env python3
import sys

#from distutils.core import setup
from extgfa.__version__ import version
from setuptools import setup, find_packages

CURRENT_PYTHON = sys.version_info[:2]
REQUIRED_PYTHON = (3, 8)

# This check and everything above must remain compatible with Python 2.7.
if CURRENT_PYTHON < REQUIRED_PYTHON:
    sys.stderr.write("extgfa requires Python 3.8 or higher and "
                     "you current version is {}".format(CURRENT_PYTHON))
    sys.exit(1)


setup(name='extgfa',
      version=version,
      description='Generating a disk-chuncked GFA graph for low-memory graph manipulations',
      author='Fawaz Dabbaghie',
      author_email='fawaz.dabbaghie@gmail.com',
      url='https://github.com/fawaz-dabbaghieh/distgfa',
      packages=find_packages(),
      # scripts=['bin/main.py'],
      license="LICENSE.TXT",
      long_description=open("README.md").read(),
      long_description_content_type='text/markdown',
      install_requires=["networkx == 3.3"],
#      install_requires=["protobuf == 3.11.3",
#                        "pystream-protobuf == 1.5.1"],
      # other arguments here...
      entry_points={
          "console_scripts": [
              "extgfa=extgfa.main:main"
          ]}
      )
