# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.http import auth_util
from gae_libs.http import http_client_appengine

from common import monitoring


class HttpClientMetricsInterceptor(auth_util.AuthenticatingInterceptor):
  """Record metrics about http requests made to external services."""

  def OnException(self, request, exception, can_retry):
    monitoring.outgoing_http_errors.increment({
        'host':
            self.GetHost(request.get('url')),
        'exception':
            "%s.%s" % (exception.__class__.__module__,
                       exception.__class__.__name__),
    })
    return super(HttpClientMetricsInterceptor, self).OnException(
        request, exception, can_retry)

  def OnResponse(self, request, response):
    monitoring.outgoing_http_statuses.increment({
        'host': self.GetHost(request.get('url')),
        'status_code': str(response.get('status_code'))
    })
    return super(HttpClientMetricsInterceptor, self).OnResponse(
        request, response)


class FinditHttpClient(http_client_appengine.HttpClientAppengine):
  """An http client for talking to external services.

  This http client has embedded authentication, retrying logic and tsmon metrics
  recording through the interceptor infrastructure (see
  libs/http/interceptor.py).
  """

  def __init__(self,
               interceptor=HttpClientMetricsInterceptor(),
               *args,
               **kwargs):
    """Constructor for the http client.

    We set the interceptor by default to HttpClientMetricsInterceptor which,
    through its inheritance chain, includes authentication, logging and metric
    collection.

    Note that the parent class takes 'follow_redirects' as an argument that
    defaults to True. This constructor passes it if given via kwargs.
    """
    super(FinditHttpClient, self).__init__(
        interceptor=interceptor, *args, **kwargs)
