# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

_NO_RETRY_CODE = [200, 302, 401, 403, 404, 409, 501]


class HttpInterceptorBase(object):
  """A modifying interceptor for http clients.

  This is a base class for interceptors that can intercept and modify:
    - A request before it is made
    - A response before it is returned to the caller
    - An exception before it is raised to the caller

  It is expected that the caller will use the returned values for each of these
  methods instead of the ones originally sent to them.
  """

  def GetAuthenticationHeaders(self, request):
    """An interceptor can override this method to produce auth headers.

    The http client is expected to call this function for every request and
    update the request's headers with the ones this function provides.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers'
    Returns: a dict containing headers to be set to the request before sending.
    """
    _ = request
    return {}

  def OnRequest(self, request):
    """Override this method to examine and/or tweak requests before sending.

    The http client is expected to call this method on every request and use its
    return value instead.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers'
    Returns: A request dict with possibly modified values.
    """
    return request

  def OnResponse(self, request, response):
    """Override to check and/or tweak status/body before returning to caller.

    Also, decide whether the request should be retried.

    The http client is expected to call this method after a response is received
    and before any retry logic is applied. The client is expected to return to
    the caller the return value of this method, modulo any retry logic that the
    client may implement.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers' for the request that was sent to obtain the response.
      - response(dict): A dict with 'status_code' and 'content' fields.
    Returns: A response dict with the same values (or possibly modified ones) as
      the 'response' arg, **and a boolean indicating whether to retry**
    """
    _ = request
    return response, response.get('status_code') not in _NO_RETRY_CODE

  def OnException(self, request, exception, can_retry):
    """Override to check and/or tweak an exception raised when sending request.

    The http client is expected to call this method with any exception raised
    when sending the request, if this method returns an exception, the client
    will raise it to the caller; if None is returned, the client may retry.

    Args:
      - request(dict): A dict with the relevant fields, such as 'url' and
        'headers' for the request that was sent to obtain the response.
      - exception(Exception): The exception raised by the underlying call.
      - can_retry(bool): Whether the caller will retry if the interceptor
        swallows the exception. Useful to take action on persistent exceptions
        and not on transient ones.
    Retruns: An exception to be raised to the caller or None.
    """
    _ = request
    _ = can_retry
    return exception


class LoggingInterceptor(HttpInterceptorBase):
  """A minimal interceptor that logs status code and url."""

  def OnResponse(self, request, response):
    # TODO(crbug.com/771390): Log headers for non-200 responses.
    logging.info('got response %d for url %s',
                 response.get('status_code', 0), request.get('url'))
    # Call the base's OnResponse to keep the retry functionality.
    return super(LoggingInterceptor, self).OnResponse(request, response)

  def OnException(self, request, exception, can_retry):
    if can_retry:
      logging.warning('got exception %s("%s") for url %s',
                      type(exception), exception.message, request.get('url'))
    else:
      logging.exception('got exception %s("%s") for url %s',
                        type(exception), exception.message, request.get('url'))
    return super(LoggingInterceptor, self).OnException(request, exception,
                                                       can_retry)
