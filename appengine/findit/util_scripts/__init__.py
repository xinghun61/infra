# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))

# TODO(katesonia): Figure out why os.getenv('APPLICATION_ID') always return
# True for local unittest.
#
# This hack is due to testing setup and code structure.
#
# The util_scripts/ are stand-alone local scripts and all those local
# scripts and utils under it should be imported starting from util_scripts/.
# For all the other modules of predator, imports starts from findit/ root dir.
sys.path.insert(0, _THIS_DIR)
