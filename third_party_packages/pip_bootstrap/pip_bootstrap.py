#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Bootstrap script for installing pip, wheel and setuptools from a folder
# containing those three wheels.
#
# This is inspired by https://bootstrap.pypa.io/get-pip.py, but extremely
# stripped down.

import os
import sys


def main():
  SCRIPT_DIR = os.path.dirname(__file__)
  PREFIX = sys.argv[1]

  # Find pip wheel in this directory.
  for filename in os.listdir(SCRIPT_DIR):
    if filename.startswith('pip-'):
      sys.path.insert(0, os.path.abspath(filename))
      break
  else:
    assert False, 'pip_bootstrap.py must be run in a directory with a pip wheel'

  # Import pip from wheel we just added to sys.path so we can use it to install
  # pip, setuptools and wheel.
  # pylint: disable=no-name-in-module
  # pylint: disable=no-member
  import pip._internal

  sys.exit(pip._internal.main([
    # obliterate whatever is there
    'install', '--upgrade', '--force-reinstall', '--ignore-installed',
    # don't talk to the internet
    '--no-index', '--find-links', SCRIPT_DIR,
    # install to this python installation
    '--prefix', PREFIX,
    # Which wheels to install
    'pip', 'setuptools', 'wheel'
  ]))
