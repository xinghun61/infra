# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys


# Note: this hacky file will be excluded during deployment to AppEngine.
# Add the checking of APPLICATION_ID is to avoid possible side-effect for local
# AppEngine dev-server.

if not os.environ.get('APPLICATION_ID'):  # pragma: no branch.
  _THIS_DIR = os.path.dirname(os.path.realpath(__file__))
  # This hack is due to testing setup and code structure.
  #
  # In testing setup, the root directory appengine/predator would be the current
  # working directory during execution of unittests; and it is automatically
  # added to sys.path or PYTHONPATH.
  #
  # For code structure, we wanted the AppEngine modules or services in separate
  # sub-directories from the root directory in order to separate the code for
  # AppEngine from those for the actual analysis -- core algorithm.
  #
  # With a module or service config file app.yaml or backend-*.yaml being in a
  # sub-directory, that sub-directory would become the current working directory
  # when the code is deployed to AppEngine or runs with AppEngine dev-server.
  # This constraint requires that module importing in the code is based off the
  # sub-directory.
  #
  # To avoid naming conflicts for module importing, we shouldn't put the *.yaml
  # files to the sub-directories app/frontend and app/backend. Otherwise
  # app/frontend and app/backend have to be added to sys.path or PYTHONPATH as
  # explained above, and that will cause naming conflicts, because both of them
  # will have same module names like handlers/, model/, etc.
  #
  # As the module or service config files *.yaml are in predator/app, it should
  # be added to sys.path so that unittests won't complain about modules being
  # not found.
  sys.path.insert(0, _THIS_DIR)

  # This hack is because the appengine_config.py is loaded by the testing setup
  # only if it is in the root directory appengine/predator.
  import appengine_config  # Unused Variable pylint: disable=W0612, W0403
