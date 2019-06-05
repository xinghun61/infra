# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Functions to help display attachments and compute quotas."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import hmac
import logging

from framework import urls
from services import secrets_svc
from tracker import tracker_helpers


VIEWABLE_IMAGE_TYPES = [
    'image/jpeg', 'image/gif', 'image/png', 'image/x-png', 'image/webp',
    ]
VIEWABLE_VIDEO_TYPES = [
    'video/ogg', 'video/mp4', 'video/mpg', 'video/mpeg', 'video/webm',
    'video/quicktime',
    ]
MAX_PREVIEW_FILESIZE = 15 * 1024 * 1024  # 15 MB


def IsViewableImage(mimetype_charset, filesize):
  """Return true if we can safely display such an image in the browser.

  Args:
    mimetype_charset: string with the mimetype string that we got back
        from the 'file' command.  It may have just the mimetype, or it
        may have 'foo/bar; charset=baz'.
    filesize: int length of the file in bytes.

  Returns:
    True iff we should allow the user to view a thumbnail or safe version
    of the image in the browser.  False if this might not be safe to view,
    in which case we only offer a download link.
  """
  mimetype = mimetype_charset.split(';', 1)[0]
  return (mimetype in VIEWABLE_IMAGE_TYPES and
          filesize < MAX_PREVIEW_FILESIZE)


def IsViewableVideo(mimetype_charset, filesize):
  """Return true if we can safely display such a video in the browser.

  Args:
    mimetype_charset: string with the mimetype string that we got back
        from the 'file' command.  It may have just the mimetype, or it
        may have 'foo/bar; charset=baz'.
    filesize: int length of the file in bytes.

  Returns:
    True iff we should allow the user to watch the video in the page.
  """
  mimetype = mimetype_charset.split(';', 1)[0]
  return (mimetype in VIEWABLE_VIDEO_TYPES and
          filesize < MAX_PREVIEW_FILESIZE)


def IsViewableText(mimetype, filesize):
  """Return true if we can safely display such a file as escaped text."""
  return (mimetype.startswith('text/') and
          filesize < MAX_PREVIEW_FILESIZE)


def SignAttachmentID(aid):
  """One-way hash of attachment ID to make it harder for people to scan."""
  digester = hmac.new(secrets_svc.GetXSRFKey())
  digester.update(str(aid))
  return base64.urlsafe_b64encode(digester.digest())


def GetDownloadURL(attachment_id):
  """Return a relative URL to download an attachment to local disk."""
  return 'attachment?aid=%s&signed_aid=%s' % (
        attachment_id, SignAttachmentID(attachment_id))


def GetViewURL(attach, download_url, project_name):
  """Return a relative URL to view an attachment in the browser."""
  if IsViewableImage(attach.mimetype, attach.filesize):
    return download_url + '&inline=1'
  elif IsViewableVideo(attach.mimetype, attach.filesize):
    return download_url + '&inline=1'
  elif IsViewableText(attach.mimetype, attach.filesize):
    return tracker_helpers.FormatRelativeIssueURL(
        project_name, urls.ISSUE_ATTACHMENT_TEXT,
        aid=attach.attachment_id)
  else:
    return None


def GetThumbnailURL(attach, download_url):
  """Return a relative URL to view an attachment thumbnail."""
  if IsViewableImage(attach.mimetype, attach.filesize):
    return download_url + '&inline=1&thumb=1'
  else:
    return None


def GetVideoURL(attach, download_url):
  """Return a relative URL to view an attachment thumbnail."""
  if IsViewableVideo(attach.mimetype, attach.filesize):
    return download_url + '&inline=1'
  else:
    return None
