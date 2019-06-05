# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittest for the tracker helpers module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from mock import Mock, patch
import unittest

from proto import tracker_pb2
from tracker import attachment_helpers


class AttachmentHelpersFunctionsTest(unittest.TestCase):

  def testIsViewableImage(self):
    self.assertTrue(attachment_helpers.IsViewableImage('image/gif', 123))
    self.assertTrue(attachment_helpers.IsViewableImage(
        'image/gif; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableImage('image/png', 123))
    self.assertTrue(attachment_helpers.IsViewableImage(
        'image/png; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableImage('image/x-png', 123))
    self.assertTrue(attachment_helpers.IsViewableImage('image/jpeg', 123))
    self.assertTrue(attachment_helpers.IsViewableImage(
        'image/jpeg; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableImage(
        'image/jpeg', 14 * 1024 * 1024))

    self.assertFalse(attachment_helpers.IsViewableImage('junk/bits', 123))
    self.assertFalse(attachment_helpers.IsViewableImage(
        'junk/bits; charset=binary', 123))
    self.assertFalse(attachment_helpers.IsViewableImage(
        'image/jpeg', 16 * 1024 * 1024))

  def testIsViewableVideo(self):
    self.assertTrue(attachment_helpers.IsViewableVideo('video/ogg', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo(
        'video/ogg; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo('video/mp4', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo(
        'video/mp4; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo('video/mpg', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo(
        'video/mpg; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo('video/mpeg', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo(
        'video/mpeg; charset=binary', 123))
    self.assertTrue(attachment_helpers.IsViewableVideo(
        'video/mpeg', 14 * 1024 * 1024))

    self.assertFalse(attachment_helpers.IsViewableVideo('junk/bits', 123))
    self.assertFalse(attachment_helpers.IsViewableVideo(
        'junk/bits; charset=binary', 123))
    self.assertFalse(attachment_helpers.IsViewableVideo(
        'video/mp4', 16 * 1024 * 1024))

  def testIsViewableText(self):
    self.assertTrue(attachment_helpers.IsViewableText('text/plain', 0))
    self.assertTrue(attachment_helpers.IsViewableText('text/plain', 1000))
    self.assertTrue(attachment_helpers.IsViewableText('text/html', 1000))
    self.assertFalse(
        attachment_helpers.IsViewableText('text/plain', 200 * 1024 * 1024))
    self.assertFalse(attachment_helpers.IsViewableText('image/jpeg', 200))
    self.assertFalse(
        attachment_helpers.IsViewableText('image/jpeg', 200 * 1024 * 1024))

  def testSignAttachmentID(self):
    pass  # TODO(jrobbins): write tests

  @patch('tracker.attachment_helpers.SignAttachmentID')
  def testGetDownloadURL(self, mock_SignAttachmentID):
    """The download URL is always our to attachment servlet."""
    mock_SignAttachmentID.return_value = 67890
    self.assertEqual(
      'attachment?aid=12345&signed_aid=67890',
      attachment_helpers.GetDownloadURL(12345))

  def testGetViewURL(self):
    """The view URL may add &inline=1, or use our text attachment servlet."""
    attach = tracker_pb2.Attachment(
        attachment_id=1, mimetype='see below', filesize=1000)
    download_url = 'attachment?aid=1&signed_aid=2'

    # Viewable image.
    attach.mimetype = 'image/jpeg'
    self.assertEqual(
      download_url + '&inline=1',
      attachment_helpers.GetViewURL(attach, download_url, 'proj'))

    # Viewable video.
    attach.mimetype = 'video/mpeg'
    self.assertEqual(
      download_url + '&inline=1',
      attachment_helpers.GetViewURL(attach, download_url, 'proj'))

    # Viewable text file.
    attach.mimetype = 'text/html'
    self.assertEqual(
      '/p/proj/issues/attachmentText?aid=1',
      attachment_helpers.GetViewURL(attach, download_url, 'proj'))

    # Something we don't support.
    attach.mimetype = 'audio/mp3'
    self.assertIsNone(
      attachment_helpers.GetViewURL(attach, download_url, 'proj'))

  def testGetThumbnailURL(self):
    """The thumbnail URL may add param thumb=1 or not."""
    attach = tracker_pb2.Attachment(
        attachment_id=1, mimetype='see below', filesize=1000)
    download_url = 'attachment?aid=1&signed_aid=2'

    # Viewable image.
    attach.mimetype = 'image/jpeg'
    self.assertEqual(
      download_url + '&inline=1&thumb=1',
      attachment_helpers.GetThumbnailURL(attach, download_url))

    # Viewable video.
    attach.mimetype = 'video/mpeg'
    self.assertIsNone(
      # Video thumbs are displayed via GetVideoURL rather than this.
      attachment_helpers.GetThumbnailURL(attach, download_url))

    # Something that we don't thumbnail.
    attach.mimetype = 'audio/mp3'
    self.assertIsNone(attachment_helpers.GetThumbnailURL(attach, download_url))

  def testGetVideoURL(self):
    """The video URL is the same as the view URL for actual videos."""
    attach = tracker_pb2.Attachment(
        attachment_id=1, mimetype='see below', filesize=1000)
    download_url = 'attachment?aid=1&signed_aid=2'

    # Viewable video.
    attach.mimetype = 'video/mpeg'
    self.assertEqual(
      download_url + '&inline=1',
      attachment_helpers.GetVideoURL(attach, download_url))

    # Anything that is not a video.
    attach.mimetype = 'audio/mp3'
    self.assertIsNone(attachment_helpers.GetVideoURL(attach, download_url))

