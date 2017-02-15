# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to log client-side javascript error reports.

Updates frontend/js_errors ts_mon metric.
"""

import json
import logging

from framework import jsonfeed

from infra_libs import ts_mon

class ClientMonitor(jsonfeed.JsonFeed):
  """JSON feed to track client side js errors in ts_mon."""

  js_errors = ts_mon.CounterMetric('frontend/js_errors',
      'Number of uncaught client-side JS errors.',
      None)

  def HandleRequest(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """

    post_data = mr.request.POST
    errors = post_data.get('errors')
    try:
      errors = json.loads(errors)

      total_errors = 0
      for error_key in errors:
        total_errors += errors[error_key]
      logging.error('client monitor report (%d): %s', total_errors,
          post_data.get('errors'))
      self.js_errors.increment_by(total_errors)
    except Exception as e:
      logging.error('Problem processing client monitor report: %r', e)

    return {}
