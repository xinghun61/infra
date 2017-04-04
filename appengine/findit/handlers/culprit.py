# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler, Permission
from model import analysis_approach_type
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

  def GetListOfTryJobBuilds(builds):
    displayed_builds = {}
    for build_id, build in builds.iteritems():
      if analysis_approach_type.TRY_JOB not in build.get('approaches', []):
        continue

      build_info = build_util.GetBuildInfoFromId(build_id)
      master_name = build_info[0]
      builder_name = build_info[1]
      build_number = build_info[2]
      if (not displayed_builds.get((master_name, builder_name)) or
          displayed_builds[(master_name, builder_name)][0] > build_number):
        displayed_builds[(master_name, builder_name)] = (build_number, )

    return [k + v for k, v in displayed_builds.iteritems()]

  if isinstance(culprit, WfCulprit):
    return map(ConvertBuildInfoToADict, culprit.builds)
  else:
    return map(ConvertBuildInfoToADict, GetListOfTryJobBuilds(culprit.builds))


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
