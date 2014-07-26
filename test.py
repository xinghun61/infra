#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Convenience script for (cd [infra] && ENV/bin/expect_tests "$@")"""

assert __name__ == '__main__'

import os
import sys

path = os.path.join('ENV', 'bin', 'expect_tests')
os.chdir(os.path.dirname(__file__))
os.execv(path, [path] + sys.argv[1:])
