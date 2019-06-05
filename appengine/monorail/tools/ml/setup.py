from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from setuptools import find_packages
from setuptools import setup

REQUIRED_PACKAGES = ['google-cloud-storage']

setup(
  name='trainer',
  version='0.1',
  install_requires=REQUIRED_PACKAGES,
  packages=find_packages(),
  include_package_data=True,
  description="""Trainer application package for training a spam classification
                 model in ML Engine and storing the saved model and accuracy
                 results in GCS."""
)
