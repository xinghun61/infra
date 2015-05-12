#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Download and run node.js."""

import imp
import os
import sys

THIS_PATH = os.path.dirname(os.path.abspath(__file__))
node_py = imp.load_source('node', os.path.join(THIS_PATH,  'node.py'))


if __name__ == '__main__':
  sys.exit(node_py.main('npm'))
