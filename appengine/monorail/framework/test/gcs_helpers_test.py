# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for the framework_helpers module."""

import unittest
import uuid

import mox

from google.appengine.api import app_identity
from google.appengine.api import images
from third_party import cloudstorage

from framework import filecontent
from framework import gcs_helpers
from testing import fake
from testing import testing_helpers


class GcsHelpersTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testDeleteObjectFromGCS(self):
    object_id = 'aaaaa'
    bucket_name = 'test_bucket'
    object_path = '/' + bucket_name + object_id

    self.mox.StubOutWithMock(app_identity, 'get_default_gcs_bucket_name')
    app_identity.get_default_gcs_bucket_name().AndReturn(bucket_name)

    self.mox.StubOutWithMock(cloudstorage, 'delete')
    cloudstorage.delete(object_path)

    self.mox.ReplayAll()

    gcs_helpers.DeleteObjectFromGCS(object_id)
    self.mox.VerifyAll()

  def testStoreObjectInGCS_ResizableMimeType(self):
    guid = 'aaaaa'
    project_id = 100
    object_id = '/%s/attachments/%s' % (project_id, guid)
    bucket_name = 'test_bucket'
    object_path = '/' + bucket_name + object_id
    mime_type = 'image/png'
    content = 'content'
    thumb_content = 'thumb_content'

    self.mox.StubOutWithMock(app_identity, 'get_default_gcs_bucket_name')
    app_identity.get_default_gcs_bucket_name().AndReturn(bucket_name)

    self.mox.StubOutWithMock(uuid, 'uuid4')
    uuid.uuid4().AndReturn(guid)

    self.mox.StubOutWithMock(cloudstorage, 'open')
    cloudstorage.open(
        object_path, 'w', mime_type, options={}
        ).AndReturn(fake.FakeFile())
    cloudstorage.open(object_path + '-thumbnail', 'w', mime_type).AndReturn(
        fake.FakeFile())

    self.mox.StubOutWithMock(images, 'resize')
    images.resize(content, gcs_helpers.DEFAULT_THUMB_WIDTH,
                  gcs_helpers.DEFAULT_THUMB_HEIGHT).AndReturn(thumb_content)

    self.mox.ReplayAll()

    ret_id = gcs_helpers.StoreObjectInGCS(
        content, mime_type, project_id, gcs_helpers.DEFAULT_THUMB_WIDTH,
        gcs_helpers.DEFAULT_THUMB_HEIGHT)
    self.mox.VerifyAll()
    self.assertEquals(object_id, ret_id)

  def testStoreObjectInGCS_NotResizableMimeType(self):
    guid = 'aaaaa'
    project_id = 100
    object_id = '/%s/attachments/%s' % (project_id, guid)
    bucket_name = 'test_bucket'
    object_path = '/' + bucket_name + object_id
    mime_type = 'not_resizable_mime_type'
    content = 'content'

    self.mox.StubOutWithMock(app_identity, 'get_default_gcs_bucket_name')
    app_identity.get_default_gcs_bucket_name().AndReturn(bucket_name)

    self.mox.StubOutWithMock(uuid, 'uuid4')
    uuid.uuid4().AndReturn(guid)

    self.mox.StubOutWithMock(cloudstorage, 'open')
    options = {'Content-Disposition': 'inline; filename="file.ext"'}
    cloudstorage.open(
        object_path, 'w', mime_type, options=options
        ).AndReturn(fake.FakeFile())

    self.mox.ReplayAll()

    ret_id = gcs_helpers.StoreObjectInGCS(
        content, mime_type, project_id, gcs_helpers.DEFAULT_THUMB_WIDTH,
        gcs_helpers.DEFAULT_THUMB_HEIGHT, filename='file.ext')
    self.mox.VerifyAll()
    self.assertEquals(object_id, ret_id)

  def testCheckMemeTypeResizable(self):
    for resizable_mime_type in gcs_helpers.RESIZABLE_MIME_TYPES:
      gcs_helpers.CheckMimeTypeResizable(resizable_mime_type)

    with self.assertRaises(gcs_helpers.UnsupportedMimeType):
      gcs_helpers.CheckMimeTypeResizable('not_resizable_mime_type')

  def testStoreLogoInGCS(self):
    file_name = 'test_file.png'
    mime_type = 'image/png'
    content = 'test content'
    project_id = 100
    object_id = 123

    self.mox.StubOutWithMock(filecontent, 'GuessContentTypeFromFilename')
    filecontent.GuessContentTypeFromFilename(file_name).AndReturn(mime_type)

    self.mox.StubOutWithMock(gcs_helpers, 'StoreObjectInGCS')
    gcs_helpers.StoreObjectInGCS(
        content, mime_type, project_id,
        thumb_width=gcs_helpers.LOGO_THUMB_WIDTH,
        thumb_height=gcs_helpers.LOGO_THUMB_HEIGHT).AndReturn(object_id)

    self.mox.ReplayAll()

    ret_id = gcs_helpers.StoreLogoInGCS(file_name, content, project_id)
    self.mox.VerifyAll()
    self.assertEquals(object_id, ret_id)
