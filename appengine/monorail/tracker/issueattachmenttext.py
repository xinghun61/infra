# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Servlet to safely display textual issue attachments.

Unlike most attachments, this is not a download, it is a full HTML page
with safely escaped user content.
"""

import logging

import webapp2

from google.appengine.api import app_identity

from third_party import cloudstorage
from third_party import ezt

from features import prettify
from framework import exceptions
from framework import filecontent
from framework import permissions
from framework import servlet
from framework import template_helpers
from tracker import tracker_bizobj
from tracker import tracker_helpers
from tracker import tracker_views


class AttachmentText(servlet.Servlet):
  """AttachmentText displays textual attachments much like source browsing."""

  _PAGE_TEMPLATE = 'tracker/issue-attachment-text.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def GatherPageData(self, mr):
    """Parse the attachment ID from the request and serve its content.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering almost the page.
    """
    with mr.profiler.Phase('get issue, comment, and attachment'):
      try:
        attachment, issue = tracker_helpers.GetAttachmentIfAllowed(
            mr, self.services)
      except exceptions.NoSuchIssueException:
        webapp2.abort(404, 'issue not found')
      except exceptions.NoSuchAttachmentException:
        webapp2.abort(404, 'attachment not found')
      except exceptions.NoSuchCommentException:
        webapp2.abort(404, 'comment not found')

    content = []
    if attachment.gcs_object_id:
      bucket_name = app_identity.get_default_gcs_bucket_name()
      full_path = '/' + bucket_name + attachment.gcs_object_id
      logging.info("reading gcs: %s" % full_path)
      with cloudstorage.open(full_path, 'r') as f:
        content = f.read()

    filesize = len(content)

    # This servlet only displays safe textual attachments. The user should
    # not have been given a link to this servlet for any other kind.
    if not tracker_views.IsViewableText(attachment.mimetype, filesize):
      self.abort(400, 'not a text file')

    u_text, is_binary, too_large = filecontent.DecodeFileContents(content)
    lines = prettify.PrepareSourceLinesForHighlighting(u_text.encode('utf8'))

    config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    granted_perms = tracker_bizobj.GetGrantedPerms(
        issue, mr.auth.effective_ids, config)
    page_perms = self.MakePagePerms(
        mr, issue, permissions.DELETE_ISSUE, permissions.CREATE_ISSUE,
        granted_perms=granted_perms)

    page_data = {
        'issue_tab_mode': 'issueDetail',
        'local_id': issue.local_id,
        'filename': attachment.filename,
        'filesize': template_helpers.BytesKbOrMb(filesize),
        'file_lines': lines,
        'is_binary': ezt.boolean(is_binary),
        'too_large': ezt.boolean(too_large),
        'code_reviews': None,
        'page_perms': page_perms,
        }
    if is_binary or too_large:
      page_data['should_prettify'] = ezt.boolean(False)
    else:
      page_data.update(prettify.BuildPrettifyData(
          len(lines), attachment.filename))

    return page_data
