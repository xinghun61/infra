# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from google.appengine.api import app_identity
from google.appengine.api import modules


def IsInDevServer():  # pragma: no cover.
  """Returns whether the code runs in dev server locally."""
  return os.environ['APPLICATION_ID'].startswith('dev')


def GetCurrentVersion():  # pragma: no cover.
  """Returns the version of this module."""
  return modules.get_current_version_name()


def GetDefaultVersionHostname():  # pragma: no cover.
  """Returns the default version hostname of this service."""
  return app_identity.get_default_version_hostname()


def GetTargetNameForModule(module_name, version=None):  # pragma: no cover.
  """Returns the target name for the given module and version.

  Version defaults to the one running this code.
  """
  if IsInDevServer():
    # Dev server doesn't support multiple versions of a module.
    return module_name
  else:
    version = version or GetCurrentVersion()
    return '%s.%s' % (version, module_name)
