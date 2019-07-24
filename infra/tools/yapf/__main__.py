#!/usr/bin/env vpython

# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# [VPYTHON:BEGIN]
# wheel: <
#   # Required for parallelism in python 2.
#   name: "infra/python/wheels/futures-py2_py3"
#   version: "version:3.1.1"
# >
# wheel: <
#   name: "infra/python/wheels/yapf-py2_py3"
#   version: "version:0.27.0"
# >
# [VPYTHON:END]

# -*- coding: utf-8 -*-
import sys

from yapf import run_main

if __name__ == '__main__':
    sys.exit(run_main())
