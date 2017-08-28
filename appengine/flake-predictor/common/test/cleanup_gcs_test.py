# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

import main
from common import cleanup_gcs
import cloudstorage
from testing_utils import testing
from time_functions.testing import mock_datetime_utc


BUCKET = '/test_bucket'
FILE_CONTENTS = 'bogus test file contents'


class CleanupGCSBucketTest(testing.AppengineTestCase):
  app_module = main.app

  def setUp(self):
    cleanup_gcs.BUCKET = BUCKET
    super(CleanupGCSBucketTest, self).setUp()

  def add_files(self, num_files):
    for i in range(num_files):
      time_uploaded = (datetime.datetime.utcnow()).strftime(
          "%Y-%m-%dT%H:%M:%SZ")
      file_name = BUCKET + '/file_' + str(i) + '_' + time_uploaded
      open_file = cloudstorage.open(file_name, 'w')
      open_file.write(FILE_CONTENTS)
      open_file.close()

  @mock_datetime_utc(2017, 8, 13, 1, 0, 0)
  def add_old_files(self, num_files):
    # Cloudstorage uses the current time when uploading files to the cloud.
    # To overwrite this, a separate function with a different mocked time
    # is used.
    self.add_files(num_files)

  @mock_datetime_utc(2017, 8, 21, 1, 0, 0)
  def test_delete_old_files(self):
    self.add_files(5)
    self.add_old_files(5)
    self.test_app.get('/internal/cleanup-gcs-handler')
    num_files = 0
    for file_stat in cloudstorage.listbucket(BUCKET):
      time_uploaded = datetime.datetime.strptime(
          datetime.datetime.fromtimestamp(
              file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
        '%Y-%m-%d %H:%M:%S')
      self.assertFalse(datetime.datetime.utcnow() - time_uploaded
                       >= datetime.timedelta(days=cleanup_gcs.DAYS))
      num_files += 1
    self.assertEqual(num_files, 5)
