# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys


def FixSysPaths():  # pragma: no cover
  # The main reason for this hack is: we want this module to be self-contained.
  # And due to testing setup in the infra repo, appengine/cr_culprit_finder
  # would be the current working directory during test execution instead of this
  # directory. But we can't import from appengine/cr_culprit_finder, because the
  # root directory for app deployment is appengine/cr_culprit_finder/service/*
  # instead.
  #
  # As a side effect, clients importing this module via symbolic links don't
  # have to explicitly add this directory to the PYTHONPATH or sys.path, because
  # it is implicitly done here.
  #
  # Add to sys.path this directory so that unittests and deployed app won't
  # complain about modules not found.
  _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
  if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

  # Analysis module depends on the first-party libs.
  # Do not add the third-party libs until needed.
  _FIRST_PARTY_DIR = os.path.join(_THIS_DIR, 'first_party')
  sys.path.insert(0, _FIRST_PARTY_DIR)


FixSysPaths()
