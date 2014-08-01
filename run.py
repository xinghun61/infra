#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper for `python -m` to make running tools simpler.

A tool is defined as a python module with a __main__.py file. This latter file
is run by the present script.

In particular, allows gclient to change directories when running hooks for
infra.
"""

assert __name__ == '__main__'

import imp
import os
import sys

RUNPY_PATH = os.path.abspath(__file__)
ROOT_PATH = os.path.dirname(RUNPY_PATH)
ENV_PATH = os.path.join(ROOT_PATH, 'ENV')

# Do not want to mess with sys.path, load the module directly.
run_helper = imp.load_source(
    'run_helper', os.path.join(ROOT_PATH, 'bootstrap', 'run_helper.py'))

sys.exit(run_helper.run_py_main(sys.argv[1:], RUNPY_PATH, ENV_PATH, 'infra'))
