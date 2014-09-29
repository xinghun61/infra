#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script to generate documentation with Sphinx."""

assert __name__ == '__main__'

import os
import subprocess

INFRA_ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ['PYTHONPATH'] += (os.path.pathsep + INFRA_ROOT)
os.chdir(INFRA_ROOT)

# Clean
subprocess.check_call(os.path.join('bootstrap', 'remove_orphaned_pycs.py'))

# Add missing rst files
path = os.path.join('ENV', 'bin', 'sphinx-apidoc')
subprocess.check_call([path, '-o', 'doc/source/reference/', 'infra/'])

# Build html documentation for rst files
path = os.path.join('ENV', 'bin', 'sphinx-build')
os.execv(path, [path, '-b', 'html', 'doc/source', 'doc/html'])
