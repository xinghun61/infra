# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement spam flagging features.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import httplib
import logging

from framework import framework_helpers
from framework import paginate
from framework import permissions
from framework import urls
from framework import servlet
from framework import template_helpers
from framework import xsrf
from tracker import spam_helpers
from tracker import tracker_bizobj


class ModerationQueue(servlet.Servlet):
  _PAGE_TEMPLATE = 'tracker/spam-moderation-queue.ezt'

  def GatherPageData(self, mr):
    if not self.CheckPerm(mr, permissions.MODERATE_SPAM):
      raise permissions.PermissionException()

    page_perms = self.MakePagePerms(
        mr, None, permissions.MODERATE_SPAM,
        permissions.EDIT_ISSUE, permissions.CREATE_ISSUE,
        permissions.SET_STAR)

    # TODO(seanmccullough): Figure out how to get the IssueFlagQueue either
    # integrated into this page data, or on its own subtab of spam moderation.
    # Also figure out the same for Comments.
    issue_items, total_count = self.services.spam.GetIssueClassifierQueue(
        mr.cnxn, self.services.issue, mr.project.project_id, mr.start, mr.num)

    issue_queue = spam_helpers.DecorateIssueClassifierQueue(mr.cnxn,
        self.services.issue, self.services.spam, self.services.user,
        issue_items)

    url_params = [(name, mr.GetParam(name)) for name in
                  framework_helpers.RECOGNIZED_PARAMS]
    p = paginate.ArtifactPagination(
        [], mr.num, mr.GetPositiveIntParam('start'),
        mr.project_name, urls.SPAM_MODERATION_QUEUE, total_count=total_count,
        url_params=url_params)

    return {
        'issue_queue': issue_queue,
        'projectname': mr.project.project_name,
        'pagination': p,
        'page_perms': page_perms,
    }
