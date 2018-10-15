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


ISSUE_CREATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/issue_create_latency', (
    'Latency between Issue Entry form submission and page load of '
    'the subsequent issue page.'
  ), field_spec=[ts_mon.StringField('client_id')])
ISSUE_UPDATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/issue_update_latency', (
    'Latency between Issue Update form submission and page load of '
    'the subsequent issue page.'
  ), field_spec=[ts_mon.StringField('client_id')])
AUTOCOMPLETE_POPULATE_LATENCY_METRIC = ts_mon.CumulativeDistributionMetric(
  'monorail/frontend/autocomplete_populate_latency', (
    'Latency between page load and autocomplete options loading.'
  ), field_spec=[ts_mon.StringField('client_id')])


class MonorailTSMonJSHandler(TSMonJSHandler):

  def __init__(self, request=None, response=None):
    super(MonorailTSMonJSHandler, self).__init__(request, response)
    self.register_metrics([
        ISSUE_CREATE_LATENCY_METRIC,
        ISSUE_UPDATE_LATENCY_METRIC,
        AUTOCOMPLETE_POPULATE_LATENCY_METRIC])

  def xsrf_is_valid(self, body):
    """This method expects the body dictionary to include two fields:
    `token` and `user_id`.
    """
    cnxn = sql.MonorailConnection()
    token = body.get('token')
    user = users.get_current_user()
    email = user.email() if user else None

    services = self.app.config.get('services')
    auth = authdata.AuthData.FromEmail(cnxn, email, services, autocreate=False)
    try:
      xsrf.ValidateToken(token, auth.user_id, xsrf.XHR_SERVLET_PATH)
      return True
    except xsrf.TokenIncorrect:
      return False
