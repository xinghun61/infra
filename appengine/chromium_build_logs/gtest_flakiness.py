# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import os.path
import sys

sys.path.append(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), 'third_party'))

import apiclient.discovery
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
import httplib2
import oauth2client.appengine


FLAKINESS_QUERY = """
  SELECT
    test_name,
    flakiness,
    num_successes,
    num_flaky_failures,
    test_suite,
    buildername
  FROM (
    SELECT
      test_name,
      SUM(flaky_failures) / (SUM(num_successes) +
                             SUM(flaky_failures)) AS flakiness,
      SUM(num_successes) as num_successes,
      SUM(flaky_failures) as num_flaky_failures,
      REGEXP_REPLACE(FIRST(test_exe), '\\\\.exe', '') as test_suite,
      FIRST(buildername) as buildername
    FROM
      sergiyb.gtest_results_continuous
    WHERE
      run_index = 0
      AND timestamp > '%(from_date)s 00:00:00'
      AND timestamp < '%(to_date)s 00:00:00'
      AND flaky_failures is not NULL
      AND num_successes is not NULL
      AND mastername = '%(master)s'
    GROUP BY
      test_name)
  WHERE
    flakiness > %(min_flakiness)f
    AND num_flaky_failures + num_successes > %(min_results)f
  ORDER BY
    flakiness DESC
"""

# A minimum number of flaky failures and successes for the flakiness data to be
# considered statistically significant. Flakiness for tests which have fewer
# data is not computed.
MIN_SIGNIFICANT_RESULTS = 50

MASTER_WHITELIST = [
    'chromium.chromiumos',
    'chromium.fyi',
    'chromium.gpu.fyi',
    'chromium.linux',
    'chromium.mac',
    'chromium.memory',
    'chromium.memory.fyi',
    'chromium.webkit',
    'chromium.webrtc',
    'chromium.webrtc.fyi',
    'chromium.win',
    'client.v8',
    'tryserver.chromium.linux',
    'tryserver.chromium.mac',
    'tryserver.chromium.win'
]

service = None


class GTestFlakiness(webapp.RequestHandler):
  """Exposes gTest flakiness data."""

  def _parse_argument(self, request, name, parser, default=None):
    """Parses an argument in the request.

    If argument is missing, returns default value. In case of parsing error, or
    if value is missing and default not provided, a ValueError exception is
    raised.

    Args:
      request: Request dictionary.
      name: Name of the argument.
      parser: A function that takes argument value and returned parsed argument.
      default: Default value for the argument. Optional.

    Returns:
      The parsed value.
    """
    value = request.get(name)
    if not value:
      if default:
        return default
      else:
        raise ValueError()

    try:
      return parser(value)
    except:
      raise ValueError()

  def _show_usage(self, response):
    """Shows usage of the API."""
    response.headers['Content-Type'] = 'text/plain'
    response.set_status(400)
    response.out.write(
        'Returns a table of flaky tests in a given time period.'
        'Request parameters:\n'
        '  master - Master name. Required. Accepted values: "%s".\n'
        '  from   - Starting date (inclusive). Required. Format: YYYY-MM-DD.\n'
        '  to     - Ending date (exclusive). Optional. Format: YYYY-MM-DD. '
        'Default value is current date on the server.\n'
        '  format - When set to "json" returns data in JSON format.\n'
        '  min_flakiness - Minimum flakiness above which a test is considered '
        'flaky.' % '", "'.join(MASTER_WHITELIST))

  def get(self):
    master = self.request.get('master')
    if master not in MASTER_WHITELIST:
      self._show_usage(self.response)
      return

    try:
      date_parser = lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date()
      from_date = self._parse_argument(self.request, 'from', date_parser)
      to_date = self._parse_argument(self.request, 'to', date_parser,
                                     datetime.date.today())
      min_flakiness = self._parse_argument(self.request, 'min_flakiness',
                                           float, 0.01)
    except Exception:
      self._show_usage(self.response)
      return

    query = FLAKINESS_QUERY % {'min_flakiness': min_flakiness,
                               'from_date': from_date.strftime('%Y-%m-%d'),
                               'to_date': to_date.strftime('%Y-%m-%d'),
                               'master': master,
                               'min_results': MIN_SIGNIFICANT_RESULTS}
    response = service.jobs().query(projectId='chromium-build-logs', body={
        'timeoutMs': 60000,  # 1 minute
        'query': query
    }).execute()

    results = []
    for row in response.get('rows', []):
      result = {}
      field_index = 0
      for field in response['schema']['fields']:
        result[field['name']] = row['f'][field_index]['v']
        field_index += 1
      results.append(result)

    if self.request.get('format') == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.out.write(json.dumps(results))
    else:
      template_path = os.path.join(os.path.dirname(__file__), 'templates',
                                   'gtest_flakiness.html')
      html = template.render(template_path, {'results': results})
      self.response.out.write(html)


def main():
  global service
  credentials = oauth2client.appengine.AppAssertionCredentials(
      scope='https://www.googleapis.com/auth/bigquery')
  http = credentials.authorize(http=httplib2.Http(timeout=60))
  service = apiclient.discovery.build('bigquery', 'v2', http=http)

  application = webapp.WSGIApplication([
      ('/flakiness/gtest', GTestFlakiness)])
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
