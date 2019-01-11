# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""ts_mon JavaScript proxy handler."""

from framework import authdata
from framework import sql
from framework import xsrf

from gae_ts_mon.handlers import TSMonJSHandler

from google.appengine.api import users

from infra_libs import ts_mon


STANDARD_FIELDS = [
  ts_mon.StringField('client_id'),
  ts_mon.StringField('host_name'),
  ts_mon.BooleanField('document_visible'),
]


# User action metrics.
ISSUE_CREATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/issue_create_latency', (
    'Latency between Issue Entry form submission and page load of '
    'the subsequent issue page.'
  ), field_spec=STANDARD_FIELDS,
  units=ts_mon.MetricsDataUnits.MILLISECONDS)
ISSUE_UPDATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/issue_update_latency', (
    'Latency between Issue Update form submission and page load of '
    'the subsequent issue page.'
  ), field_spec=STANDARD_FIELDS,
  units=ts_mon.MetricsDataUnits.MILLISECONDS)
AUTOCOMPLETE_POPULATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/autocomplete_populate_latency', (
    'Latency between page load and autocomplete options loading.'
  ), field_spec=STANDARD_FIELDS,
  units=ts_mon.MetricsDataUnits.MILLISECONDS)

# Page load metrics.
DOM_CONTENT_LOADED_EXTRA_FIELDS = [
    ts_mon.StringField('template_name')]
DOM_CONTENT_LOADED_METRIC = ts_mon.CumulativeDistributionMetric(
  'frontend/dom_content_loaded', (
    'domContentLoaded performance timing.'
  ), field_spec=STANDARD_FIELDS + DOM_CONTENT_LOADED_EXTRA_FIELDS,
  units=ts_mon.MetricsDataUnits.MILLISECONDS)


class MonorailTSMonJSHandler(TSMonJSHandler):

  def __init__(self, request=None, response=None):
    super(MonorailTSMonJSHandler, self).__init__(request, response)
    self.register_metrics([
        ISSUE_CREATE_LATENCY_METRIC,
        ISSUE_UPDATE_LATENCY_METRIC,
        AUTOCOMPLETE_POPULATE_LATENCY_METRIC,
        DOM_CONTENT_LOADED_METRIC])

  def xsrf_is_valid(self, _body):
    """This method expects the body dictionary to include two fields:
    `token` and `user_id`.
    """
    # TODO(4420): Reinstate XSRF checking after QPS from old versions
    # has gone down.
    return True
