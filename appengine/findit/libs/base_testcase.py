# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

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


class BaseTestCase(unittest.TestCase):  # pragma: no cover.

  def MockUTCNow(self, mocked_utcnow):
    """Mocks utcnow with the given value for testing."""
    self.mock(time_util, 'GetUTCNow', lambda: mocked_utcnow)

  def GetMockHttpClient(self, response_for_url=None):
    """Returns mocked http client class."""
    return MockHttpClient(response_for_url or {})

  def GetMockRepoFactory(self, response_for_url=None):
    """Returns mocked repository factory."""
    return GitilesRepository.Factory(
        self.GetMockHttpClient(response_for_url or {}))
