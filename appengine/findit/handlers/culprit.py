# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.base_handler import BaseHandler, Permission
from waterfall import build_util


def _FormatDatetime(dt):
  if not dt:
    return None  # pragma: no cover
  else:
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


class Culprit(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Lists the build cycles in which the culprit caused failures."""
    key = self.request.get('key', '')

    culprit = ndb.Key(urlsafe=key).get()
    if not culprit:  # pragma: no cover
      return self.CreateError('Culprit not found', 404)

    def ConvertBuildInfoToADict(build_id):
      build_info = build_util.GetBuildInfoFromId(build_id)
      return {
          'master_name': build_info[0],
          'builder_name': build_info[1],
          'build_number': build_info[2],
      }

    data = {
        'project_name': culprit.project_name,
        'revision': culprit.revision,
        'commit_position': culprit.commit_position,
        'cr_notified': culprit.cr_notified,
        'cr_notification_time': _FormatDatetime(culprit.cr_notification_time),
        'builds': map(ConvertBuildInfoToADict, culprit.builds),
        'key': key,
    }
    return {'template': 'waterfall/culprit.html', 'data': data}
