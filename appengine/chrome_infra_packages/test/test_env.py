# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prepares process state to run tests. Imported from all test files.

Bunch of hacks essentially to patch GAE code to run in unit tests environment.
"""

import contextlib
import os

# TODO(vadimsh): Figure out why this is required. Without it warmup test fails.
os.environ['APPLICATION_ID'] = 'test_app'
os.environ['SERVER_SOFTWARE'] = 'Development unittest'
os.environ['CURRENT_VERSION_ID'] = 'default-version.123'

from testing_utils import testing
import frontend


# expect_test coverage engine refuses to calculate coverage for this file.
class EndpointsApiTestCase(testing.AppengineTestCase):  # pragma: no cover
  # Should be set in subclasses.
  API_CLASS_NAME = None

  @property
  def app_module(self):
    return frontend.create_endpoints_app()

  def call_api(self, method, body=None, status=None):
    """Calls endpoints API method identified by its function name."""
    return self.test_app.post_json(
        '/_ah/spi/%s.%s' % (self.API_CLASS_NAME, method),
        body or {},
        status=status)

  @contextlib.contextmanager
  def should_fail(self, _status):
    # This should be a call_api(..., status=<something>). Unfortunately,
    # Cloud Endpoints doesn't interact with webtest properly. See
    # https://code.google.com/p/googleappengine/issues/detail?id=10544 and
    # http://stackoverflow.com/questions/24219654/content-length-error-in-
    #   google-cloud-endpoints-testing
    with self.assertRaises(AssertionError):
      yield
