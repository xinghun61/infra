# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import alerts
import webapp2

from components import auth

class InternalAlertsHandler(alerts.AlertsHandler):
  ALERT_TYPE = 'internal-alerts'

  # Has no 'request' member.
  # Has no 'response' member.
  # Use of super on an old style class.
  # pylint: disable=E1002,E1101
  @auth.public
  def get(self):
    # Require users to be logged to see builder alerts from private/internal
    # trees.

    user = auth.get_current_identity()
    if user.is_anonymous:
      ret = {}
      ret.update({
          'date': datetime.datetime.utcnow(),
          'redirect-url': self.create_login_url(self.request.uri)
      })
      data = self.generate_json_dump(ret)
      self.send_json_headers()
      self.response.write(data)
      return

    if not auth.is_group_member('googlers'):
      self.response.set_status(403, 'Permission Denied')
      return

    super(InternalAlertsHandler, self).get()


app = webapp2.WSGIApplication([
    ('/internal-alerts', InternalAlertsHandler)])
