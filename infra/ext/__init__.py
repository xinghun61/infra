# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

def _add_ext_dirs_to_path():
  base = os.path.dirname(os.path.abspath(__file__))

  for d in os.listdir(base):
    full = os.path.join(base, d)
    if os.path.isdir(full):
      # TODO(iannucci): look for egg
      sys.path.insert(0, full)
      globals()[d] = __import__(d)

_add_ext_dirs_to_path()

# Enough of a hint for pylint / jedi (autocompletion) to find and follow the
# imports, but doesn't make python import them immediately at runtime.
#
# This list should always contain a complete list of all modules in ext.
if False:
  import requests
  import argcomplete

class _LazyImportHack(object):
  def __getattr__(self, name):
    mod = __import__(name)
    setattr(self, name, mod)
    return mod

sys.modules[__name__] = _LazyImportHack()
