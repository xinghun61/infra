# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.base_handler import BaseHandler, Permission
from model.wf_culprit import WfCulprit
from waterfall import build_util


def _FormatDatetime(dt):
  if not dt:
    return None  # pragma: no cover
  else:
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def _GetBuildInfoAsDict(culprit):
  """Returns the list of failed builds associated with the given culprit."""
  def ConvertBuildInfoToADict(build_info):
    return {
        'master_name': build_info[0],
        'builder_name': build_info[1],
        'build_number': build_info[2],
    }

  def ConvertBuildIdToADict(build_id):
    build_info = build_util.GetBuildInfoFromId(build_id)
    return ConvertBuildInfoToADict(build_info)

  if isinstance(culprit, WfCulprit):
    return map(ConvertBuildInfoToADict, culprit.builds)
  else:
    return map(ConvertBuildIdToADict, culprit.builds)


class Culprit(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Lists the build cycles in which the culprit caused failures."""
    key = self.request.get('key', '')

    culprit = ndb.Key(urlsafe=key).get()
    if not culprit:  # pragma: no cover
      return self.CreateError('Culprit not found', 404)

    data = {
        'project_name': culprit.project_name,
        'revision': culprit.revision,
        'commit_position': culprit.commit_position,
        'cr_notified': culprit.cr_notified,
        'cr_notification_time': _FormatDatetime(culprit.cr_notification_time),
        'builds': _GetBuildInfoAsDict(culprit),
        'key': key,
    }
    return {'template': 'waterfall/culprit.html', 'data': data}
