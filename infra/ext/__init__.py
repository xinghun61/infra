# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

# Explicit import paths for sub-projects that don't follow the
# 'infra/ext/<package>/<package>/' directory layout.
EXTPACKAGES = {
    'httplib2': os.path.join('httplib2', 'python' + str(sys.version_info[0])),
    'pytz': os.path.join('pytz', 'src'),
    }


def _add_ext_dirs_to_path():
  base = os.path.dirname(os.path.abspath(__file__))

  for d in os.listdir(base):
    full = os.path.join(base, EXTPACKAGES.get(d, d))
    if os.path.isdir(full):
      # TODO(iannucci): look for egg
      # Needed to support absolute imports in sub-projects (e.g. pytz has
      # imports like: from pytz.exceptions import AmbiguousTimeError).
      sys.path.insert(0, full)
      # Needed to support 'import infra.ext.foo' syntax.
      __path__.append(full)

_add_ext_dirs_to_path()

# Enough of a hint for pylint / jedi (autocompletion) to find and follow the
# imports, but doesn't make python import them immediately at runtime.
#
# This list should always contain a complete list of all modules in ext.
if False:
  import argcomplete
  import dateutil
  import httplib2
  import oauth2client
  import pytz
  import requests
