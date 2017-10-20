# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement spam flagging features.
"""

import httplib
import logging

from framework import actionlimit
from framework import framework_helpers
from framework import paginate
from framework import permissions
from framework import urls
from framework import servlet
from framework import template_helpers
from framework import xsrf
from tracker import spam_helpers

class FlagSpamForm(servlet.Servlet):
  """Flag or un-flag the specified issue/comment for the logged in user."""

  _CAPTCHA_ACTION_TYPES = [actionlimit.FLAG_SPAM]

  def ProcessFormData(self, mr, post_data):
    """Process the flagging request.
    Args:
      mr: commonly used info parsed from the request.

    Returns:
      A redirect URL to either the original issue page or to issue list.
    """
    comment_id = post_data.get('comment_id', 0) or None

    flagged_spam = post_data['spam'] == 'true'

    flag_count = 1
    if mr.local_id_list is not None:
      flag_count = len(mr.local_id_list)

    self.CountRateLimitedActions(mr, {actionlimit.FLAG_SPAM: flag_count})
    # Has the side effect of checking soft limits and returning an error page
    # when the user hits the limit.
    self.GatherCaptchaData(mr)

    # Check perms here for both the single Issue and Comment case.
    if mr.local_id is not None:
      issue = self.services.issue.GetIssueByLocalID(
          mr.cnxn, mr.project_id, mr.local_id, use_cache=False)
      perms = self.MakePagePerms(
          mr, issue, permissions.FLAG_SPAM, permissions.VERDICT_SPAM)
      if not perms.FlagSpam:
        logging.error('User %d not allowed to flag %d/%r as spam.' % (
            mr.auth.user_id, mr.local_id, comment_id))
        raise permissions.PermissionException(
            'User lacks permission to flag spam')

    # TODO: Check for exceeding the max number of flags, issue verdict then too.

    issue_list = []
    # Flag a single comment.
    if comment_id is not None:
      comment = self.services.issue.GetComment(mr.cnxn, comment_id)
      if perms.VerdictSpam:
        self.services.spam.RecordManualCommentVerdict(mr.cnxn,
            self.services.issue, self.services.user, comment_id,
            mr.auth.user_id, flagged_spam)

      self.services.spam.FlagComment(mr.cnxn, issue.issue_id, comment.id,
          comment.user_id, mr.auth.user_id, flagged_spam)

    elif mr.local_id is not None:
      issue_list = [issue]
    elif mr.local_id_list is not None:
      issue_list = self.services.issue.GetIssuesByLocalIDs(
          mr.cnxn, mr.project_id, mr.local_id_list, use_cache=False)
    else:
      self.response.status = httplib.BAD_REQUEST
      return

    flag_issues = []
    verdict_issues = []
    for issue in issue_list:
      perms = self.MakePagePerms(mr, issue, permissions.FLAG_SPAM,
           permissions.VERDICT_SPAM)
      if perms.VerdictSpam:
        verdict_issues.append(issue)
      if perms.FlagSpam:
        flag_issues.append(issue)

    if len(verdict_issues) > 0:
      self.services.spam.RecordManualIssueVerdicts(mr.cnxn, self.services.issue,
          verdict_issues,  mr.auth.user_id, flagged_spam)

    if len(flag_issues) > 0:
      self.services.spam.FlagIssues(mr.cnxn, self.services.issue, flag_issues,
          mr.auth.user_id, flagged_spam)

    # TODO(seanmccullough): Make this an ajax request instead of a redirect.
    if mr.local_id_list is not None:
      return framework_helpers.FormatAbsoluteURL(mr, urls.ISSUE_LIST)
    else:
      return framework_helpers.FormatAbsoluteURL(
          mr, urls.ISSUE_DETAIL, id=mr.local_id)


class ModerationQueue(servlet.Servlet):
  _PAGE_TEMPLATE = 'tracker/spam-moderation-queue.ezt'

  def ProcessFormData(self, mr, post_data):
    if not self.CheckPerm(mr, permissions.MODERATE_SPAM):
      raise permissions.PermissionException()

    issue_local_ids = [int(iid) for iid in post_data.getall("issue_local_id")]
    mark_spam = "mark_spam" in post_data

    issues = self.services.issue.GetIssuesByLocalIDs(mr.cnxn,
        mr.project.project_id, issue_local_ids, use_cache=False)

    self.services.spam.RecordManualIssueVerdicts(mr.cnxn,
        self.services.issue, issues, mr.auth.user_id, mark_spam)

    return framework_helpers.FormatAbsoluteURL(mr, urls.SPAM_MODERATION_QUEUE)

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

    p = paginate.ArtifactPagination(mr, [], mr.num, urls.SPAM_MODERATION_QUEUE,
        total_count)

    return {
        'issue_queue': issue_queue,
        'projectname': mr.project.project_name,
        'pagination': p,
        'page_perms': page_perms,
        'moderate_spam_token': xsrf.GenerateToken(
            mr.auth.user_id, '/p/%s%s.do' % (
                mr.project_name, urls.SPAM_MODERATION_QUEUE)),
    }
