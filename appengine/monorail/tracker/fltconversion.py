# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""FLT task to be manually triggered to convert launch issues."""

import settings

from framework import permissions
from framework import exceptions
from framework import jsonfeed

class FLTConvertTask(jsonfeed.InternalTask):
  """FLTConvert converts current Type=Launch issues into Type=FLT-Launch."""


  def AssertBasePermission(self, mr):
    super(FLTConvertTask, self).AssertBasePermission(mr)
    if not mr.auth.user_pb.is_site_admin:
      raise permissions.PermissionException(
          'Only site admins may trigger conversion job')
    if settings.app_id != 'monorail-staging':
      raise exceptions.ActionNotSupported(
          'Launch issues conversion only allowed in staging.')

  def HandleRequest(self, mr):
    """Convert Type=Launch issues to new Type=FLT-Launch issues."""


    return {
        'app_id': settings.app_id,
        'is_site_admin': mr.auth.user_pb.is_site_admin,
        }
