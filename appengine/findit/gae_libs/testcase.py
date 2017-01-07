# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from testing_utils import testing

from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs import time_util
from libs.gitiles.gitiles_repository import GitilesRepository
from libs.http import retry_http_client


class MockHttpClient(retry_http_client.RetryHttpClient):  # pragma: no cover.

  def __init__(self, response_for_url=None):
    super(MockHttpClient, self).__init__()
    self.response_for_url = response_for_url or {}

  def SetResponseForUrl(self, url, response):
    self.response_for_url[url] = response

  def GetBackoff(self, *_):
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, *_):
    response = self.response_for_url.get(url)
    if response is None:
      return 404, 'Not Found'
    else:
      return 200, response

  def _Post(self, *_):
    pass

  def _Put(self, *_):
    pass


class TestCase(testing.AppengineTestCase):  # pragma: no cover.
  # Setup the customized queues.
  taskqueue_stub_root_path = os.path.join(
    os.path.dirname(__file__), os.path.pardir)

  def MockPipeline(
      self, pipeline_class, result, expected_args, expected_kwargs=None):
    """Mocks a pipeline to return a value and asserts the expected parameters.

    Args:
      pipeline_class (class): The class of the pipeline to be mocked.
      result (object): The result to be returned by the pipeline.
      expected_args (list): The list of positional parameters expected by the
          pipeline.
      expected_kwargs (dict): The dict of key-value parameters expected by the
          pipeline. Default is None.
    """
    expected_kwargs = expected_kwargs or {}

    def Mocked_run(_, *args, **kwargs):
      self.assertEqual(list(args), expected_args)
      self.assertEqual(kwargs, expected_kwargs)
      return result

    self.mock(pipeline_class, 'run', Mocked_run)

  def MockUTCNow(self, mocked_utcnow):
    """Mocks utcnow with the given value for testing."""
    self.mock(time_util, 'GetUTCNow', lambda: mocked_utcnow)

  def MockUTCNowWithTimezone(self, mocked_utcnow):
    """Mocks utcnow with the given value for testing."""
    self.mock(time_util, 'GetUTCNowWithTimezone', lambda: mocked_utcnow)

  def GetMockHttpClient(self, response_for_url=None):
    """Returns mocked http client class."""
    return MockHttpClient(response_for_url)
