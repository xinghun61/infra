# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from google.appengine.api import app_identity
from google.appengine.api import modules


def IsInProduction():  # pragma: no cover.
  """Returns whether the code runs in App Engine production environment."""
  # In unit test environment, SERVER_SOFTWARE="Development/1.0 (testbed)".
  # In dev app server environment, SERVER_SOFTWARE="Development/2.0".
  # On App Engine production sever, SERVER_SOFTWARE="Google App Engine.*".
  return os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine')


def IsInDevServer():  # pragma: no cover.
  """Returns whether the code runs in dev server locally."""
  # In unit test environment, APPLICATION_ID="testbed-test".
  # In dev app server environment, APPLICATION_ID="dev~APPID".
  return os.getenv('APPLICATION_ID', '').startswith('dev')


def IsInUnitTestEnvironment():  # pragma: no cover.
  """Returns true if in unittest environment."""
  return not IsInProduction() and not IsInDevServer()


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
  if not IsInProduction():
    # Dev server doesn't support multiple versions of a module.
    return module_name
  else:
    version = version or GetCurrentVersion()
    return '%s.%s' % (version, module_name)
