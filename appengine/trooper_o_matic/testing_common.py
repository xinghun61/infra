# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common functions for unit tests."""
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map


def StubUrlfetch(responses, stub=None):
  """Stub out url fetch for unit tests.

  Args:
    responses: Dict mapping url -> dict of response 'content', 'statuscode'
    stub: apiproxy_stub.APIProxyStub used to stub out urlfetch, if using testbed
  """
  fetch_mock = FetchServiceMock(responses)
  if stub:
    # pylint: disable=W0212
    stub._Dynamic_Fetch = fetch_mock._Dynamic_Fetch
  else:
    apiproxy_stub_map.apiproxy.RegisterStub('urlfetch', fetch_mock)


class FetchServiceMock(apiproxy_stub.APIProxyStub):
  """Mock URLFetch service used byt StubUrlfetch."""

  def __init__(self, responses):
    self.responses = responses
    super(FetchServiceMock, self).__init__('urlfetch')

  def _Dynamic_Fetch(self, request, response):
    url = request.url()
    assert url in self.responses
    response.set_content(self.responses[url]['content'])
    response.set_statuscode(self.responses[url]['statuscode'])
